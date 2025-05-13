// src/pages/AdminDashboard/menuConfig.js
import DashboardIcon from "@mui/icons-material/Dashboard";
import AssessmentIcon from "@mui/icons-material/Assessment";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import NotificationsIcon from "@mui/icons-material/Notifications";
import SettingsIcon from "@mui/icons-material/Settings";
import GroupIcon from "@mui/icons-material/Group";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import WaterDropIcon from "@mui/icons-material/WaterDrop";
import BoltIcon from "@mui/icons-material/Bolt";
import LocalGasStationIcon from "@mui/icons-material/LocalGasStation";
import OpacityIcon from "@mui/icons-material/Opacity";
import SpeedIcon from "@mui/icons-material/Speed";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import WarningIcon from "@mui/icons-material/Warning";
import UploadFileIcon from "@mui/icons-material/UploadFile";

const menuConfig = [
  {
    label: "Dashboard",
    icon: DashboardIcon,
    path: "/admin",
  },
  {
    label: "Carbon Reporting",
    icon: AssessmentIcon,
    path: "/admin/reporting",
  },
  {
    label: "Data Sources",
    icon: CloudUploadIcon,
    path: "/admin/data-sources",
  },
  {
    label: "Notifications",
    icon: NotificationsIcon,
    path: "/admin/notifications",
  },
  {
    label: "Project Settings",
    icon: SettingsIcon,
    path: "/admin/project-settings",
  },
  {
    label: "Water",
    icon: WaterDropIcon,
    path: "/admin/water",
    subMenu: [
      { label: "Overview", icon: OpacityIcon, path: "/admin/water/overview" },
      { label: "Meter Readings", icon: SpeedIcon, path: "/admin/water/meters" },
      { label: "Import Data", icon: UploadFileIcon, path: "/admin/water/import" },
      { label: "Module Settings", icon: SettingsIcon, path: "/admin/water/settings" },
      { label: "Leak Detection", icon: ReportProblemIcon, path: "/admin/water/leaks" },
    ],
  },
  {
    label: "Electricity",
    icon: BoltIcon,
    path: "/admin/electricity",
    subMenu: [
      { label: "Analytics", icon: AssessmentIcon, path: "/admin/electricity/analytics" },
      { label: "Meter Readings", icon: SpeedIcon, path: "/admin/electricity/meters" },
      { label: "Import Data", icon: UploadFileIcon, path: "/admin/electricity/import" },
      { label: "Module Settings", icon: SettingsIcon, path: "/admin/electricity/settings" },
      { label: "Outage Reports", icon: WarningIcon, path: "/admin/electricity/outages" },
    ],
  },
  {
    label: "Gas",
    icon: LocalGasStationIcon,
    path: "/admin/gas",
    subMenu: [
      { label: "Trends", icon: AssessmentIcon, path: "/admin/gas/trends" },
      { label: "Meter Readings", icon: SpeedIcon, path: "/admin/gas/meters" },
      { label: "Import Data", icon: UploadFileIcon, path: "/admin/gas/import" },
      { label: "Module Settings", icon: SettingsIcon, path: "/admin/gas/settings" },
      { label: "Safety Alerts", icon: ReportProblemIcon, path: "/admin/gas/alerts" },
    ],
  },
  {
    label: "User Management",
    icon: GroupIcon,
    path: "/admin/users",
  },
  {
    label: "Help",
    icon: HelpOutlineIcon,
    path: "/admin/help",
  },
];

export default menuConfig;