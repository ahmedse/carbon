// src/widgets/WidgetRegistry.js
import TotalEmissionsCard from './TotalEmissionsCard';
import WaterCard from './WaterCard';
import EmissionsTrendChart from './EmissionsTrendChart';
import WaterTrendChart from './WaterTrendChart';
// Add more as needed

export const WIDGETS = [
  {
    type: "summary",
    key: "totalEmissions",
    label: "Total CO₂ Emissions",
    component: TotalEmissionsCard,
    icon: "insert_chart", // Choose your icons
    always: true, // always show
  },
  {
    type: "summary",
    key: "totalWater",
    label: "Total Water Consumption",
    component: WaterCard,
    icon: "water_drop",
    always: true,
  },
  {
    type: "chart",
    key: "emissionsTrend",
    label: "CO₂ Emissions Trend",
    component: EmissionsTrendChart,
    icon: "show_chart",
  },
  {
    type: "chart",
    key: "waterTrend",
    label: "Water Trend",
    component: WaterTrendChart,
    icon: "show_chart",
  },
  // ...etc
];