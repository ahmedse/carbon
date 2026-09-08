// src/components/Wizard/Wizard.jsx
// Reusable multi-step wizard (Stepper shell) — the standard pattern for any
// multi-field create/edit flow that exceeds ~6 fields (design-system RULE 2:
// reuse before create; ux-patterns.md "Multi-Step / Wizards").
//
// Ownership contract:
//   - The Wizard owns navigation + step index + a per-step error summary.
//   - The consumer owns the form state and supplies each step's `validate`
//     (returns { valid, errors }) and `content` (node or render fn).
//
// `content` may be a React node or a function `(ctx) => node` receiving
// `{ errors, clearErrors }` so a step can render its own inline field errors.

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Step,
  StepLabel,
  Stepper,
} from '@mui/material';

function StepContent({ content, errors, clearErrors }) {
  if (typeof content === 'function') {
    return content({ errors, clearErrors });
  }
  return content;
}

StepContent.propTypes = {
  content: PropTypes.oneOfType([PropTypes.node, PropTypes.func]).isRequired,
  errors: PropTypes.arrayOf(PropTypes.string),
  clearErrors: PropTypes.func,
};

function Wizard({
  steps,
  onFinish,
  onCancel,
  onStepChange,
  initialStep = 0,
  finishLabel = 'Submit',
  nextLabel = 'Next',
  backLabel = 'Back',
  cancelLabel = 'Cancel',
  submitting = false,
  disableFinish = false,
}) {
  const [activeStep, setActiveStep] = useState(initialStep);
  const [stepErrors, setStepErrors] = useState({});

  const isLast = activeStep === steps.length - 1;

  const setStep = (index) => {
    setActiveStep(index);
    if (onStepChange) onStepChange(index);
  };

  const clearErrors = () => setStepErrors((prev) => ({ ...prev, [activeStep]: undefined }));

  const handleNext = () => {
    const step = steps[activeStep];
    if (step && typeof step.validate === 'function') {
      const result = step.validate();
      const invalid = result === false
        || (result && result.valid === false)
        || (result && Array.isArray(result.errors) && result.errors.length > 0);
      if (invalid) {
        const errors = result && Array.isArray(result.errors)
          ? result.errors
          : (result && Array.isArray(result) ? result : ['Invalid input']);
        setStepErrors((prev) => ({ ...prev, [activeStep]: errors }));
        return;
      }
    }
    if (isLast) {
      onFinish();
      return;
    }
    setStep(activeStep + 1);
  };

  const handleBack = () => {
    if (activeStep === 0) {
      if (onCancel) onCancel();
      return;
    }
    setStep(activeStep - 1);
  };

  const errors = stepErrors[activeStep];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Stepper activeStep={activeStep} alternativeLabel sx={{ flexShrink: 0, mb: 2 }}>
        {steps.map((step, i) => (
          <Step key={step.key || i}>
            <StepLabel>{step.label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {errors && errors.length > 0 && (
        <Alert
          severity="error"
          onClose={clearErrors}
          sx={{ mb: 2 }}
        >
          {errors.length === 1 ? errors[0] : (
            <ul style={{ margin: 0, paddingInlineStart: 18 }}>
              {errors.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
        </Alert>
      )}

      <Box sx={{ flexGrow: 1, overflow: 'auto', minHeight: 0 }}>
        <StepContent
          content={steps[activeStep].content}
          errors={errors}
          clearErrors={clearErrors}
        />
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
        <Box>
          {onCancel && activeStep > 0 && (
            <Button onClick={onCancel} color="inherit" size="small">
              {cancelLabel}
            </Button>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button onClick={handleBack} disabled={submitting} size="small">
            {activeStep === 0 && onCancel ? cancelLabel : backLabel}
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={submitting || (isLast && disableFinish)}
            size="small"
          >
            {isLast ? finishLabel : nextLabel}
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

Wizard.propTypes = {
  steps: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string,
      label: PropTypes.string.isRequired,
      content: PropTypes.oneOfType([PropTypes.node, PropTypes.func]).isRequired,
      validate: PropTypes.func,
    }),
  ).isRequired,
  onFinish: PropTypes.func.isRequired,
  onCancel: PropTypes.func,
  onStepChange: PropTypes.func,
  initialStep: PropTypes.number,
  finishLabel: PropTypes.string,
  nextLabel: PropTypes.string,
  backLabel: PropTypes.string,
  cancelLabel: PropTypes.string,
  submitting: PropTypes.bool,
  disableFinish: PropTypes.bool,
};

export default Wizard;
