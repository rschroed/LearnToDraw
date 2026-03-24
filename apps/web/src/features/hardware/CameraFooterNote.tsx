interface CameraFooterNoteProps {
  note: string;
}

export function CameraFooterNote({ note }: CameraFooterNoteProps) {
  return <p className="footer-note">{note}</p>;
}
