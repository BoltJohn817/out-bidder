interface ErrorMessageProps {
  message: string | null;
  className?: string;
}

export const ErrorMessage = ({ message, className = '' }: ErrorMessageProps) => {
  if (!message) return null;

  return (
    <p className={`text-sm text-red-400 ${className}`}>
      {message}
    </p>
  );
};

