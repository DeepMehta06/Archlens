export const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.wav'];
export const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(',');
export const MAX_FILE_SIZE = 20 * 1024 * 1024;
export const SUPPORTED_HINT = 'Supported: .txt .md .pdf .png .jpg .webp .wav';
export const UPLOAD_TOOLTIP = `${SUPPORTED_HINT} — up to 20 MB. PDFs over 30 pages are truncated; audio over 10 minutes isn't accepted.`;

export function validateFile(file: File): { ok: true } | { ok: false; message: string } {
  const name = file.name.toLowerCase();
  const hasAcceptedExtension = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!hasAcceptedExtension) {
    return { ok: false, message: SUPPORTED_HINT };
  }
  if (file.size > MAX_FILE_SIZE) {
    return { ok: false, message: 'That file is over the 20 MB limit.' };
  }
  return { ok: true };
}
