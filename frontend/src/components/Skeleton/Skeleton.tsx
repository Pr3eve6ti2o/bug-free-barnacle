import React from 'react';
import './Skeleton.css';

export interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  className?: string;
}

const toCssSize = (value: string | number): string =>
  typeof value === 'number' ? `${value}px` : value;

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = 16,
  radius = 8,
  className,
}) => {
  return (
    <div
      className={className ? `sh-skeleton ${className}` : 'sh-skeleton'}
      style={{
        width: toCssSize(width),
        height: toCssSize(height),
        borderRadius: toCssSize(radius),
      }}
      aria-hidden="true"
    />
  );
};

export default Skeleton;
