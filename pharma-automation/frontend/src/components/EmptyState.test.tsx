import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import EmptyState from './EmptyState';

describe('EmptyState', () => {
  it('renders default message', () => {
    render(<EmptyState />);
    expect(screen.getByText('데이터가 없습니다')).toBeInTheDocument();
  });

  it('renders custom message', () => {
    render(<EmptyState message="알림이 없습니다" />);
    expect(screen.getByText('알림이 없습니다')).toBeInTheDocument();
  });
});
