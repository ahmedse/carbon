// SearchSelect — empty-string option must resolve (filter "All"), not blank.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SearchSelect from '../components/Form/SearchSelect';

describe('SearchSelect empty-string option', () => {
  it('shows the All option label when value is empty string', () => {
    render(
      <SearchSelect
        label="Status"
        options={[
          { value: '', label: 'All' },
          { value: 'submitted', label: 'Submitted' },
        ]}
        value=""
        onChange={vi.fn()}
        clearable={false}
      />,
    );

    expect(screen.getByDisplayValue('All')).toBeInTheDocument();
  });
});
