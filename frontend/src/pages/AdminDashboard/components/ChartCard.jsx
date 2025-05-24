// File: frontend/src/pages/AdminDashboard/components/ChartCard.jsx
// Purpose: Card component to render either a line or pie chart using recharts.
// Location: frontend/src/pages/AdminDashboard/components/

import React from "react";
import { Card, CardContent, Typography } from "@mui/material";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";

const COLORS = ["#388e3c", "#1976d2", "#ffa726", "#f44336", "#8e24aa"];

/**
 * ChartCard component.
 * Renders a line or pie chart with a title.
 *
 * @param {string} title - Chart title.
 * @param {"line"|"pie"} type - Type of chart to render.
 * @param {array} data - Data array for the chart.
 */
const ChartCard = ({ title, type, data }) => (
  <Card sx={{ height: 320, borderRadius: 3, boxShadow: 2 }}>
    <CardContent>
      <Typography variant="subtitle1" fontWeight={600} mb={2}>
        {title}
      </Typography>
      <ResponsiveContainer width="100%" height={240}>
        {type === "line" ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#388e3c"
              strokeWidth={3}
              dot={{ r: 4 }}
            />
          </LineChart>
        ) : (
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={70}
              label
            >
              {data.map((entry, idx) => (
                <Cell key={`cell-${idx}`} fill={COLORS[idx % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        )}
      </ResponsiveContainer>
    </CardContent>
  </Card>
);

export default ChartCard;