import type { ReactNode } from 'react';

type CardVariant = 'default' | 'warning' | 'danger' | 'info';

const ACCENT_COLORS: Record<CardVariant, string> = {
  default: 'border-l-gray-300',
  warning: 'border-l-orange-400',
  danger: 'border-l-red-500',
  info: 'border-l-blue-400',
};

interface CardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  variant?: CardVariant;
  borderAccent?: boolean;
  padding?: 'sm' | 'md';
}

export default function Card({
  children,
  className = '',
  onClick,
  variant = 'default',
  borderAccent = false,
  padding = 'sm',
}: CardProps) {
  const pad = padding === 'sm' ? 'p-3' : 'p-4';
  const accent = borderAccent ? `border-l-4 ${ACCENT_COLORS[variant]}` : '';
  const interactive = onClick ? 'cursor-pointer hover:shadow-md transition-shadow duration-150' : '';

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl shadow-sm border border-gray-100 ${pad} ${accent} ${interactive} ${className}`}
    >
      {children}
    </div>
  );
}
