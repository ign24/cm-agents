interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function Logo({ size = 'md', className }: LogoProps) {
  const sizes = {
    sm: 'h-16 w-auto',
    md: 'h-18 w-auto',
    lg: 'h-20 w-auto'
  };

  return (
    <div className={`flex items-center ${className}`}>
      <img
        src="/logo.svg"
        alt="CM Agents"
        className={`${sizes[size]} object-contain`}
      />
    </div>
  );
}
