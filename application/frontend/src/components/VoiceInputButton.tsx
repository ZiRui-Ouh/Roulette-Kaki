import { useState, useRef, useEffect } from "react";
import { Mic, Square, Loader2, AlertCircle } from "lucide-react";
import { transcribeAudio } from "../api";
import { convertBlobToWav, blobToBase64, cleanSpeakerTags } from "../lib/audioUtils";
import type { ApiError } from "../types";

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "md";
}

// Records audio, sends it for transcription, and returns text to the input.
export default function VoiceInputButton({
  onTranscript,
  disabled = false,
  className = "",
  size = "md",
}: VoiceInputButtonProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [duration, setDuration] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const recordingStartTimeRef = useRef<number>(0);

  // Clear timer and stop audio on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopTracks();
    };
  }, []);

  // Auto-dismiss error message after 6 seconds
  useEffect(() => {
    if (errorMessage) {
      const t = setTimeout(() => setErrorMessage(null), 6000);
      return () => clearTimeout(t);
    }
  }, [errorMessage]);

  const stopTracks = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // ignore
        }
      });
      streamRef.current = null;
    }
  };

  const getSupportedMimeType = (): string => {
    if (typeof MediaRecorder === "undefined") return "audio/webm";
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
      "audio/wav",
    ];
    for (const type of candidates) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "audio/webm";
  };

  const handleStartRecording = async () => {
    setErrorMessage(null);

    // Browser compatibility check
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
      setErrorMessage("Audio recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const mimeType = getSupportedMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error("MediaRecorder error:", event);
        setErrorMessage("Recording encountered an issue. Please try again.");
        cleanupRecording();
      };

      recorder.onstop = async () => {
        const recordingDuration = Date.now() - recordingStartTimeRef.current;
        stopTracks();

        if (recordingDuration < 500 || audioChunksRef.current.length === 0) {
          setErrorMessage("Recording was too short. Please speak clearly into the microphone.");
          setIsTranscribing(false);
          setIsRecording(false);
          return;
        }

        const actualMime = recorder.mimeType || mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: actualMime });

        if (audioBlob.size === 0) {
          setErrorMessage("No audio recorded. Please try again.");
          setIsTranscribing(false);
          setIsRecording(false);
          return;
        }

        await processAudio(audioBlob, actualMime);
      };

      recordingStartTimeRef.current = Date.now();
      recorder.start(250); // 250ms timeslice chunks
      setIsRecording(true);
      setDuration(0);

      timerRef.current = window.setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);
    } catch (err: unknown) {
      console.error("Microphone access error:", err);
      stopTracks();
      setIsRecording(false);

      if (err instanceof DOMException) {
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setErrorMessage("Microphone permission denied. Please allow microphone access in your browser.");
          return;
        }
        if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          setErrorMessage("No microphone found on your device.");
          return;
        }
      }
      setErrorMessage("Could not access microphone. Please check permissions.");
    }
  };

  const handleStopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      setIsTranscribing(true);
      setIsRecording(false);
      try {
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.error("Error stopping recorder:", err);
        cleanupRecording();
      }
    } else {
      cleanupRecording();
    }
  };

  const cleanupRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    stopTracks();
    setIsRecording(false);
    setIsTranscribing(false);
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
  };

  const processAudio = async (blob: Blob, mime: string) => {
    try {
      let audioToSend = blob;
      let mimeToSend = mime;

      // Convert browser WebM/Opus audio to standard 16kHz mono WAV PCM
      try {
        audioToSend = await convertBlobToWav(blob);
        mimeToSend = "audio/wav";
      } catch (convErr) {
        console.warn("WAV conversion fallback; sending raw recorded blob:", convErr);
      }

      // Convert Blob to base64 string
      const base64Data = await blobToBase64(audioToSend);

      // Send to backend endpoint /transcribe
      const transcript = await transcribeAudio(base64Data, mimeToSend);
      const cleaned = cleanSpeakerTags(transcript);

      if (!cleaned) {
        setErrorMessage("No speech detected. Please speak clearly and try again.");
      } else {
        onTranscript(cleaned);
        setErrorMessage(null);
      }
    } catch (err: unknown) {
      console.error("Transcription failed:", err);
      const apiErr = err as ApiError;
      if (apiErr?.error === "meralion_auth_error") {
        setErrorMessage("MERaLiON API key is missing or invalid on the backend.");
      } else if (apiErr?.error === "meralion_rate_limit") {
        setErrorMessage("MERaLiON rate limit exceeded. Please wait a moment.");
      } else if (apiErr?.message) {
        setErrorMessage(`Transcription error: ${apiErr.message}`);
      } else {
        setErrorMessage("Unable to transcribe audio. Please check network connection.");
      }
    } finally {
      setIsTranscribing(false);
      cleanupRecording();
    }
  };

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins}:${remainder.toString().padStart(2, "0")}`;
  };

  const buttonSizeClass = size === "sm" ? "w-8 h-8 rounded-lg" : "w-10 h-10 rounded-xl";
  const iconSizeClass = size === "sm" ? "w-4 h-4" : "w-5 h-5";

  return (
    <div className="relative inline-flex items-center">
      {/* Recording indicator with timer badge */}
      {isRecording && (
        <div className="absolute right-full mr-2 flex items-center gap-1.5 px-2.5 py-1 bg-red-500 text-white rounded-full text-xs font-semibold shadow-xs animate-pulse whitespace-nowrap select-none">
          <span className="w-2 h-2 rounded-full bg-white animate-ping" />
          <span>Recording {formatTime(duration)}</span>
        </div>
      )}

      {/* Transcribing indicator badge */}
      {isTranscribing && (
        <div className="absolute right-full mr-2 flex items-center gap-1.5 px-2.5 py-1 bg-indigo-600 text-white rounded-full text-xs font-semibold shadow-xs whitespace-nowrap select-none">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          <span>Transcribing MERaLiON…</span>
        </div>
      )}

      {/* Main Microphone / Stop Button */}
      <button
        type="button"
        onClick={isRecording ? handleStopRecording : handleStartRecording}
        disabled={disabled || isTranscribing}
        className={`inline-flex items-center justify-center shrink-0 transition cursor-pointer shadow-xs ${buttonSizeClass} ${
          isRecording
            ? "bg-red-600 hover:bg-red-700 text-white ring-4 ring-red-100 animate-pulse"
            : isTranscribing
            ? "bg-indigo-100 text-indigo-600 cursor-wait"
            : "bg-stone-100 hover:bg-stone-200 text-stone-700 hover:text-stone-900 border border-stone-300/80"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${className}`}
        title={
          isRecording
            ? "Click to stop recording"
            : isTranscribing
            ? "Transcribing with MERaLiON..."
            : "Voice Input (Speech-to-Text via MERaLiON)"
        }
        aria-label={
          isRecording
            ? "Stop voice recording"
            : "Start voice recording with MERaLiON speech-to-text"
        }
      >
        {isRecording ? (
          <Square className={`${iconSizeClass} fill-current`} />
        ) : isTranscribing ? (
          <Loader2 className={`${iconSizeClass} animate-spin`} />
        ) : (
          <Mic className={iconSizeClass} />
        )}
      </button>

      {/* Error Notification Tooltip / Banner */}
      {errorMessage && (
        <div className="absolute bottom-full mb-2 right-0 z-50 min-w-[240px] max-w-[320px] p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl shadow-md flex items-start gap-2 animate-in fade-in slide-in-from-bottom-1">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
          <div className="flex-1 leading-snug">
            <div className="font-semibold text-red-800">Voice Input</div>
            <div>{errorMessage}</div>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-red-400 hover:text-red-700 cursor-pointer text-sm leading-none ml-1"
            title="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}
