interface LogoProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function Logo({ size = 'md', className }: LogoProps) {
  const sizes = {
    sm: 'h-8 w-auto',
    md: 'h-10 w-auto',
    lg: 'h-12 w-auto'
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