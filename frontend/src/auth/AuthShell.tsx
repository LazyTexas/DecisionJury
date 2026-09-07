// 登录 / 注册共用外壳：居中卡片 + 品牌标题（主题自适应）
import type { ReactNode } from 'react';

export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">DecisionJury</div>
        {title && <div className="auth-title">{title}</div>}
        {subtitle && <div className="auth-sub">{subtitle}</div>}
        {children}
      </div>
    </div>
  );
}