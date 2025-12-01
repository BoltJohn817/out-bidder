interface EmptyStateProps {
  message: string;
  className?: string;
}

export const EmptyState = ({ message, className = '' }: EmptyStateProps) => {
  return (
    <p className={`text-sm text-slate-400 ${className}`}>
      {message}
    </p>
  );
};

