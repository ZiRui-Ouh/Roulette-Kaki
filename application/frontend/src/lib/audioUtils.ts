/**
 * Audio conversion utilities for speech-to-text.
 *
 * Converts browser-recorded audio (WebM/Opus, MP4, etc.) into standard
 * 16,000 Hz, 16-bit Mono linear PCM WAV files.
 *
 * This uses the browser's built-in Web Audio API (AudioContext) without any
 * external dependencies, ensuring compatibility with ASR services like MERaLiON.
 */

/**
 * Encodes an AudioBuffer into standard 16-bit linear PCM WAV format.
 */
function encodeWav(audioBuffer: AudioBuffer, targetSampleRate: number = 16000): Blob {
  const numChannels = 1; // Convert to Mono for speech recognition
  const sourceSampleRate = audioBuffer.sampleRate;
  const sourceData = audioBuffer.getChannelData(0);

  // Resample to target sample rate (16,000 Hz is standard for ASR models)
  let samples: Float32Array;
  if (sourceSampleRate === targetSampleRate) {
    samples = sourceData;
  } else {
    const ratio = sourceSampleRate / targetSampleRate;
    const newLength = Math.round(sourceData.length / ratio);
    samples = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const sourceIndex = i * ratio;
      const lower = Math.floor(sourceIndex);
      const upper = Math.min(lower + 1, sourceData.length - 1);
      const weight = sourceIndex - lower;
      samples[i] = sourceData[lower] * (1 - weight) + sourceData[upper] * weight;
    }
  }

  const bytesPerSample = 2; // 16-bit PCM
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = targetSampleRate * blockAlign;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // Helper to write ASCII strings
  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  // RIFF identifier
  writeString(0, "RIFF");
  // File length minus RIFF identifier and length bytes
  view.setUint32(4, 36 + dataSize, true);
  // RIFF type
  writeString(8, "WAVE");

  // Format chunk identifier
  writeString(12, "fmt ");
  // Format chunk length
  view.setUint32(16, 16, true);
  // Sample format (1 = Linear PCM)
  view.setUint16(20, 1, true);
  // Channel count
  view.setUint16(22, numChannels, true);
  // Sample rate
  view.setUint32(24, targetSampleRate, true);
  // Byte rate (sample rate * block align)
  view.setUint32(28, byteRate, true);
  // Block align (channel count * bytes per sample)
  view.setUint16(32, blockAlign, true);
  // Bits per sample
  view.setUint16(34, 16, true);

  // Data chunk identifier
  writeString(36, "data");
  // Data chunk length
  view.setUint32(40, dataSize, true);

  // Write 16-bit PCM samples (clamped between -1.0 and 1.0)
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const intSample = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, intSample, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

/**
 * Converts any audio Blob (e.g. WebM/Opus) into a 16kHz mono WAV Blob.
 */
export async function convertBlobToWav(audioBlob: Blob): Promise<Blob> {
  const AudioContextClass =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

  if (!AudioContextClass) {
    throw new Error("Web Audio API AudioContext not supported in this browser.");
  }

  const audioContext = new AudioContextClass();
  try {
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    return encodeWav(audioBuffer, 16000);
  } finally {
    try {
      await audioContext.close();
    } catch {
      // ignore
    }
  }
}

/**
 * Converts a Blob to a raw base64 string (without the data: MIME prefix).
 */
export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      const commaIndex = result.indexOf(",");
      if (commaIndex !== -1) {
        resolve(result.substring(commaIndex + 1));
      } else {
        resolve(result);
      }
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Strips speaker tags like `<Speaker1>: `, `[Speaker 1]: `, `Speaker 1: ` from transcripts.
 */
export function cleanSpeakerTags(text: string): string {
  if (!text) return "";
  let cleaned = text.replace(/[<\[]\s*speaker[\s_-]*\d*\s*[>\]]\s*[:：]?\s*/gi, "");
  cleaned = cleaned.replace(/(?:^|\n)\s*speaker[\s_-]*\d*\s*[:：]\s*/gi, "\n");
  cleaned = cleaned.replace(/(?:^|\n)\s*speaker\s*[:：]\s*/gi, "\n");
  return cleaned.trim();
}
