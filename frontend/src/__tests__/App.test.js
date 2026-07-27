import { render, screen } from '@testing-library/react';
import App from '../App';

test('renders landing page by default', () => {
  render(<App />);
  const headings = screen.getAllByText(/prof_ia/i);
  expect(headings.length).toBeGreaterThan(0);
});
