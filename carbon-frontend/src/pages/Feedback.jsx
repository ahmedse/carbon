import React, { useState } from "react";
import {
  Box, Paper, Typography, TextField, Button, Rating, Alert, CircularProgress,
} from "@mui/material";
import FeedbackIcon from "@mui/icons-material/Feedback";
import { apiFetch } from "../api/api";
import { API_ROUTES } from "../config";

export default function Feedback() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    feedback: "",
    rating: 4,
  });
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
  };

  const handleRating = (e, value) => {
    setForm(f => ({ ...f, rating: value }));
  };

  const handleSubmit = async (e) => {
  e.preventDefault();
  setError("");
  setBusy(true);

  try {
    await apiFetch(API_ROUTES.feedback, {
      method: "POST",
      body: {
        name: form.name,
        email: form.email,
        message: form.feedback,
        rating: form.rating,
      },
      // No token required for feedback, unless you want only authenticated users
      token: null,
    });
    setSubmitted(true);
  } catch (err) {
    setError(err.message);
  } finally {
    setBusy(false);
  }
};

  if (submitted) {
    return (
      <Box maxWidth={500} mx="auto" mt={7}>
        <Paper elevation={3} sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
          <FeedbackIcon color="success" sx={{ fontSize: 48, mb: 2 }} />
          <Typography variant="h5" fontWeight={700} mb={2}>
            Thank you for your feedback!
          </Typography>
          <Typography variant="body1">
            We appreciate your input. Our team will review your message.
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box maxWidth={500} mx="auto" mt={7}>
      <Paper elevation={3} sx={{ p: 4, borderRadius: 3 }}>
        <Box display="flex" alignItems="center" mb={3}>
          <FeedbackIcon color="primary" sx={{ fontSize: 40, mr: 2 }} />
          <Typography variant="h4" fontWeight={700}>
            Feedback
          </Typography>
        </Box>
        <Typography variant="body1" mb={2} color="text.secondary">
          This system is under active development. Please share your suggestions, comments, or report issues below!
        </Typography>
        <form onSubmit={handleSubmit} autoComplete="off">
          <TextField
            label="Your Name (optional)"
            name="name"
            value={form.name}
            onChange={handleChange}
            fullWidth
            margin="normal"
          />
          <TextField
            label="Your Email (optional)"
            name="email"
            value={form.email}
            onChange={handleChange}
            fullWidth
            margin="normal"
            type="email"
          />
          <TextField
            label="Your Feedback"
            name="feedback"
            value={form.feedback}
            onChange={handleChange}
            fullWidth
            margin="normal"
            required
            multiline
            rows={4}
          />
          <Box mt={2} mb={2}>
            <Typography variant="subtitle1" fontWeight={500}>
              Rate your experience:
            </Typography>
            <Rating
              name="rating"
              value={form.rating}
              onChange={handleRating}
              size="large"
            />
          </Box>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={busy}
            sx={{ mt: 2, fontWeight: 700, fontSize: 16 }}
            size="large"
          >
            {busy ? <CircularProgress size={24} /> : "Send Feedback"}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}