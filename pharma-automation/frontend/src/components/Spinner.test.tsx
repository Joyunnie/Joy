import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Spinner from './Spinner';

describe('Spinner', () => {
  it('renders with default height', () => {
    const { container } = render(<Spinner />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveClass('h-40');
  });

  it('renders with custom height', () => {
    const { container } = render(<Spinner containerHeight="h-64" />);
    const wrapper = container.firstElementChild;
    expect(wrapper).toHaveClass('h-64');
  });

  it('contains spinning element', () => {
    const { container } = render(<Spinner />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });
});
