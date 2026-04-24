import type { CSSProperties, ReactNode } from "react";

interface ArtifactCardProps {
  className?: string;
  title: string;
  imageUrl?: string | null;
  alt?: string;
  emptyMessage: string;
  footer?: string | null;
  headerActions?: ReactNode;
  frameStyle?: CSSProperties;
  frameContent?: ReactNode;
}

export function ArtifactCard({
  className,
  title,
  imageUrl,
  alt,
  emptyMessage,
  footer,
  headerActions,
  frameStyle,
  frameContent,
}: ArtifactCardProps) {
  return (
    <article className={className ? `artifact-card ${className}` : "artifact-card"}>
      <header className="artifact-card-header">
        <h3>{title}</h3>
        {headerActions ? <div className="artifact-card-actions">{headerActions}</div> : null}
      </header>
      <div className="artifact-frame" style={frameStyle}>
        {frameContent ? (
          frameContent
        ) : imageUrl ? (
          <img src={imageUrl} alt={alt ?? title} />
        ) : (
          <div className="empty-state">{emptyMessage}</div>
        )}
      </div>
      {footer ? <p className="artifact-footer">{footer}</p> : null}
    </article>
  );
}
