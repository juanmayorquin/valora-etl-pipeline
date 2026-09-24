import React from 'react';

export type LogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface LogoProps {
  className?: string;
  size?: LogoSize;
  alt?: string;
  variant?: string;
}

export const Logo: React.FC<LogoProps> = ({
  className = '',
  size = 'md',
  alt = 'VALORA',
}) => {
  const sizeClasses: Record<LogoSize, string> = {
    xs: 'h-7 w-auto',
    sm: 'h-8 sm:h-9 w-auto',
    md: 'h-10 sm:h-11 w-auto',
    lg: 'h-12 sm:h-14 w-auto',
    xl: 'h-16 sm:h-20 w-auto',
  };

  return (
    <div className={`flex items-center ${className}`}>
      <img
        src="/logo-transparent.png"
        alt={alt}
        className={`${sizeClasses[size]} w-auto object-contain`}
      />
    </div>
  );
};
