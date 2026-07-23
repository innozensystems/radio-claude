document.addEventListener("DOMContentLoaded", () => {
  const radioApp = document.getElementById("radio-app");
  const HLS_URL = radioApp.dataset.streamUrl;
  // Chromium uses hls.js/Media Source instead of native HLS. Operators can
  // provide a separate browser-compatible rendition when the primary stream
  // contains codecs that Media Source cannot append reliably.
  const HLS_JS_URL = radioApp.dataset.hlsFallbackUrl;
  const HLS_LIBRARY_URL =
    "https://cdn.jsdelivr.net/npm/hls.js@1.6.16/dist/hls.min.js";
  const HLS_LIBRARY_INTEGRITY =
    "sha384-5E8B0pTlZZJMabWpC0fyYf6OUpe15jJij34BqBAh4NXoHAlLNOjCPRrwtOXOQFAn";
  const METADATA_URL = radioApp.dataset.metadataUrl;
  const COVER_URL = radioApp.dataset.coverUrl;
  const METADATA_POLL_MS = 5000;
  const RATE_STATUS_URL = "/rate-status";
  const RATE_URL = "/rate";
  const NATIVE_STREAM_QUALITY = "Native HLS";
  const HLS_JS_STREAM_QUALITY = "HLS";

  const audioPlayer = document.getElementById("audio-player");
  const playBtn = document.getElementById("play-btn");
  const muteBtn = document.getElementById("mute-btn");
  const volumeSlider = document.getElementById("volume-slider");
  const npCover = document.getElementById("np-cover");
  const npTitle = document.getElementById("np-title");
  const npArtist = document.getElementById("np-artist");
  const npAlbum = document.getElementById("np-album");
  const sourceQualityEl = document.getElementById("source-quality");
  const streamQualityEl = document.getElementById("stream-quality");
  const historyList = document.getElementById("history-list");
  const rateUpBtn = document.getElementById("rate-up");
  const rateDownBtn = document.getElementById("rate-down");
  const rateUpCount = document.getElementById("rate-up-count");
  const rateDownCount = document.getElementById("rate-down-count");
  const ratingMsg = document.getElementById("rating-msg");
  const trackTimerEl = document.getElementById("track-timer");

  let hls = null;
  let hlsLibraryPromise = null;
  let usingHlsJs = false;
  let playbackAttached = false;
  let metadataTimer = null;
  let currentMetadata = null;
  let trackStartTime = null;
  let trackTimerInterval = null;
  function onPlay() {
    playBtn.textContent = "⏸";
    playBtn.classList.add("playing");
    startMetadataPolling();
    startTrackTimer(false);
  }

  function onStop() {
    playBtn.textContent = "▶";
    playBtn.classList.remove("playing");
    stopMetadataPolling();
    stopTrackTimer();
  }

  function attachNativeHls() {
    audioPlayer.src = HLS_URL;
    playbackAttached = true;
  }

  function loadHlsLibrary() {
    if (typeof Hls !== "undefined") return Promise.resolve();
    if (hlsLibraryPromise) return hlsLibraryPromise;

    hlsLibraryPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = HLS_LIBRARY_URL;
      script.integrity = HLS_LIBRARY_INTEGRITY;
      script.crossOrigin = "anonymous";
      script.async = true;
      script.addEventListener("load", resolve, { once: true });
      script.addEventListener(
        "error",
        () => reject(new Error("Unable to load hls.js")),
        { once: true },
      );
      document.head.appendChild(script);
    });

    return hlsLibraryPromise;
  }

  async function attachHlsJs() {
    await loadHlsLibrary();
    if (typeof Hls === "undefined" || !Hls.isSupported()) {
      throw new Error("HLS not supported in this browser");
    }

    hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
      backBufferLength: 90,
      autoStartLoad: false,
    });

    hls.loadSource(HLS_JS_URL);
    hls.attachMedia(audioPlayer);
    playbackAttached = true;

    hls.on(Hls.Events.ERROR, (event, data) => {
      if (data.fatal) {
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            console.warn("Network error — retrying");
            hls.startLoad();
            break;
          case Hls.ErrorTypes.MEDIA_ERROR:
            console.warn("Media error — recovering");
            hls.recoverMediaError();
            break;
          default:
            console.warn("Fatal stream error");
            hls.destroy();
            hls = null;
            playbackAttached = false;
            break;
        }
      }
    });

  }

  function init() {
    // Recent Chromium versions report that they can play HLS natively, but
    // still fail to demux this stream (DEMUXER_ERROR_COULD_NOT_PARSE). Keep
    // Chromium on the hls.js compatibility path and reserve native HLS for
    // browsers such as Safari.
    const isChromium =
      navigator.userAgentData?.brands?.some((brand) =>
        /Chromium|Google Chrome|Microsoft Edge/.test(brand.brand),
      ) || /(?:Chrome|Chromium|CriOS|Edg)\//.test(navigator.userAgent);
    const hasNativeHls = Boolean(
      audioPlayer.canPlayType("application/vnd.apple.mpegurl"),
    );

    if (hasNativeHls && !isChromium) {
      streamQualityEl.textContent = NATIVE_STREAM_QUALITY;
    } else {
      streamQualityEl.textContent = HLS_JS_STREAM_QUALITY;
      usingHlsJs = true;
    }
  }

  async function ensurePlaybackAttached() {
    if (playbackAttached) return;
    if (usingHlsJs) {
      await attachHlsJs();
    } else {
      attachNativeHls();
    }
  }

  function renderHistory(metadata) {
    const previous = [];
    for (let i = 1; i <= 5; i++) {
      const artist = metadata[`prev_artist_${i}`];
      const title = metadata[`prev_title_${i}`];
      if (artist && title) {
        previous.push({ artist, title });
      }
    }

    historyList.innerHTML = "";

    if (previous.length === 0) {
      historyList.innerHTML = '<li class="empty">No recent tracks</li>';
      return;
    }

    previous.forEach((track) => {
      const li = document.createElement("li");

      const titleEl = document.createElement("span");
      titleEl.className = "hist-title";
      titleEl.textContent = track.title;

      const artistEl = document.createElement("span");
      artistEl.className = "hist-artist";
      artistEl.textContent = track.artist;

      li.appendChild(titleEl);
      li.appendChild(artistEl);
      historyList.appendChild(li);
    });
  }

  function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60);
    const s = String(Math.floor(totalSeconds % 60)).padStart(2, "0");
    return `${m}:${s}`;
  }

  let bufferedMetadata = null;

  function displayTrack(metadata) {
    const title = metadata.title || "Unknown title";
    const artist = metadata.artist || "Unknown artist";
    const album = metadata.album;
    const year = metadata.date;
    const bitDepth = metadata.bit_depth;
    const sampleRate = metadata.sample_rate;

    npTitle.textContent = title;
    npArtist.textContent = artist;

    let albumText = "";
    if (album) {
      albumText += `Album: ${album}`;
      if (year) {
        albumText += ` (${year})`;
      }
    } else if (year) {
      albumText += `Year: ${year}`;
    }
    npAlbum.textContent = albumText;

    if (bitDepth && sampleRate) {
      const khz = (sampleRate / 1000).toFixed(1);
      sourceQualityEl.textContent = `${bitDepth}-bit ${khz} kHz`;
    } else {
      sourceQualityEl.textContent = "—";
    }

    // Refresh rating state for the new track
    fetchRatingStatus(metadata);
  }

  function updateTrackTimer() {
    if (!trackStartTime) return;
    const elapsedSeconds = Math.floor((Date.now() - trackStartTime) / 1000);
    trackTimerEl.textContent = formatTime(elapsedSeconds);
  }

  function startTrackTimer(reset = true) {
    if (trackTimerInterval) {
      clearInterval(trackTimerInterval);
    }
    if (reset || !trackStartTime) trackStartTime = Date.now();
    updateTrackTimer();
    if (audioPlayer.paused || document.hidden) return;
    trackTimerInterval = setInterval(updateTrackTimer, 1000);
  }

  function stopTrackTimer() {
    if (!trackTimerInterval) return;
    clearInterval(trackTimerInterval);
    trackTimerInterval = null;
  }

  function getTrackKey(metadata) {
    return `${metadata.title}|${metadata.artist}|${metadata.album}`;
  }

  function commitBufferedTrack() {
    if (!bufferedMetadata) return;
    currentMetadata = bufferedMetadata;
    displayTrack(bufferedMetadata);
    renderHistory(bufferedMetadata);
    startTrackTimer();
    // Changing only the fragment triggers an image refresh while preserving
    // normal HTTP cache/revalidation behavior for the shared cover URL.
    npCover.src = `${COVER_URL}#${encodeURIComponent(
      getTrackKey(bufferedMetadata),
    )}`;
    bufferedMetadata = null;
  }

  function maybeBufferNewTrack(metadata) {
    const newTrackKey = getTrackKey(metadata);
    const oldTrackKey = currentMetadata ? getTrackKey(currentMetadata) : null;
    if (newTrackKey !== oldTrackKey) {
      bufferedMetadata = metadata;
    }
  }

  function renderNowPlaying(metadata) {
    // Nothing to do here any more; displayTrack handles the UI.
    // Kept as a no-op placeholder to avoid breaking callers during refactor.
  }

  function updateRatingUI(summary, userRating) {
    rateUpCount.textContent = summary.up_count;
    rateDownCount.textContent = summary.down_count;

    rateUpBtn.classList.remove("active-up");
    rateDownBtn.classList.remove("active-down");

    if (userRating === "up") {
      rateUpBtn.classList.add("active-up");
      ratingMsg.textContent = "You liked this song";
    } else if (userRating === "down") {
      rateDownBtn.classList.add("active-down");
      ratingMsg.textContent = "You disliked this song";
    } else {
      ratingMsg.textContent = "";
    }
  }

  async function fetchRatingStatus(metadata) {
    if (!metadata || !metadata.title) return;
    const params = new URLSearchParams({
      title: metadata.title,
      artist: metadata.artist || "",
      album: metadata.album || "",
    });
    try {
      const response = await fetch(`${RATE_STATUS_URL}?${params.toString()}`);
      if (!response.ok) return;
      const summary = await response.json();
      updateRatingUI(summary, summary.user_rating);
    } catch (err) {
      console.error("Rating status error:", err);
    }
  }

  async function submitRating(rating) {
    if (!currentMetadata || !currentMetadata.title) return;
    try {
      const response = await fetch(RATE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: currentMetadata.title,
          artist: currentMetadata.artist || "",
          album: currentMetadata.album || "",
          rating,
        }),
      });
      const result = await response.json();
      if (response.ok) {
        updateRatingUI(result, rating);
      } else {
        console.warn("Rating failed:", result.error);
      }
    } catch (err) {
      console.error("Rating submit error:", err);
    }
  }

  rateUpBtn.addEventListener("click", () => submitRating("up"));
  rateDownBtn.addEventListener("click", () => submitRating("down"));

  async function fetchMetadata() {
    try {
      const response = await fetch(METADATA_URL, { cache: "no-store" });
      if (!response.ok) {
        console.warn("Metadata fetch failed:", response.status);
        return;
      }
      const metadata = await response.json();
      maybeBufferNewTrack(metadata);

      // On first load, commit immediately so the UI isn't empty.
      if (!currentMetadata) {
        commitBufferedTrack();
        return;
      }

      // For a continuous live HLS stream, the <audio> "ended" event does not
      // fire at song boundaries, and the backend's is_new flag is not reliably
      // set for this stream. Commit as soon as the polled title/artist changes
      // so the cover, title, and timer stay in sync with the audio. The
      // configured metadata and cover endpoints are expected to represent the
      // same current track.
      if (bufferedMetadata) {
        const bufferedKey = getTrackKey(bufferedMetadata);
        const currentKey = getTrackKey(currentMetadata);
        if (bufferedKey !== currentKey) {
          commitBufferedTrack();
        }
      }
    } catch (err) {
      console.error("Error fetching metadata:", err);
    }
  }

  function startMetadataPolling() {
    fetchMetadata();
    if (metadataTimer) {
      clearInterval(metadataTimer);
    }
    metadataTimer = setInterval(fetchMetadata, METADATA_POLL_MS);
  }

  function stopMetadataPolling() {
    if (!metadataTimer) return;
    clearInterval(metadataTimer);
    metadataTimer = null;
  }

  function updateMuteIcon() {
    const volume = audioPlayer.muted ? 0 : audioPlayer.volume;
    if (volume === 0) {
      muteBtn.textContent = "🔇";
    } else if (volume < 0.5) {
      muteBtn.textContent = "🔉";
    } else {
      muteBtn.textContent = "🔊";
    }
  }

  function setVolume(value) {
    const volume = parseFloat(value);
    audioPlayer.volume = volume;
    audioPlayer.muted = volume === 0;
    volumeSlider.value = volume;
    updateMuteIcon();
  }

  muteBtn.addEventListener("click", () => {
    if (audioPlayer.muted || audioPlayer.volume === 0) {
      // Unmute: restore previous volume or default to 1
      const previousVolume = parseFloat(volumeSlider.dataset.previousVolume || "1");
      setVolume(previousVolume > 0 ? previousVolume : 1);
    } else {
      // Mute: remember current volume, then set to 0
      volumeSlider.dataset.previousVolume = audioPlayer.volume;
      setVolume(0);
    }
  });

  volumeSlider.addEventListener("input", () => {
    setVolume(volumeSlider.value);
    if (audioPlayer.volume > 0) {
      volumeSlider.dataset.previousVolume = audioPlayer.volume;
    }
  });

  audioPlayer.addEventListener("volumechange", updateMuteIcon);
  audioPlayer.addEventListener("playing", onPlay);
  audioPlayer.addEventListener("pause", onStop);
  audioPlayer.addEventListener("ended", onStop);
  audioPlayer.addEventListener("error", () => {
    console.warn("Stream error");
    onStop();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopMetadataPolling();
      stopTrackTimer();
    } else if (!audioPlayer.paused) {
      startMetadataPolling();
      startTrackTimer(false);
    }
  });

  playBtn.addEventListener("click", async () => {
    // Toggle based on the element's actual paused state so the button never
    // gets out of sync with the audio element.
    if (!audioPlayer.paused) {
      audioPlayer.pause();
      if (hls) {
        hls.stopLoad();
      }
      return;
    }

    try {
      await ensurePlaybackAttached();
      if (hls) hls.startLoad();
      await audioPlayer.play();
    } catch (err) {
      console.warn("Playback failed — check browser autoplay policy");
      console.error(err);
    }
  });

  init();
  // Populate now-playing content without downloading audio or repeatedly
  // polling until the listener starts playback.
  fetchMetadata();
  setVolume(1);
  updateMuteIcon();
});
