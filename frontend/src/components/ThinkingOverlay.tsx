// 分析过程状态卡（主题自适应）
export default function ThinkingOverlay({
  active,
  title,
  description,
}: {
  active: boolean;
  title?: string;
  description?: string;
}) {
  if (!active) return null;

  return (
    <div className="spin-card">
      <span className="spinner" />
      <div>
        <div style={{ fontWeight: 600 }}>{title ?? '处理中…'}</div>
        {description && <div className="tiny" style={{ color: 'var(--ink3)' }}>{description}</div>}
      </div>
    </div>
  );
}