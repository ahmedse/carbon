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
    label: "Data Schema",
    icon: CloudUploadIcon,
    path: "/admin/data-schema",
    subMenu: [
      {
        label: "Data Items",
        icon: CloudUploadIcon,
        path: "/admin/data-schema/data-items",
      },
      {
        label: "Templates",
        icon: CloudUploadIcon,
        path: "/admin/data-schema/templates",
      },
    ],
  },
  {
    label: "Water",
    icon: WaterDropIcon,
    path: "/admin/water",
    dynamicTemplates: true,
    moduleName: "water",
  },
  {
    label: "Electricity",
    icon: BoltIcon,
    path: "/admin/electricity",
    dynamicTemplates: true,
    moduleName: "electricity",
  },
  {
    label: "Gas",
    icon: LocalGasStationIcon,
    path: "/admin/gas",
    dynamicTemplates: true,
    moduleName: "gas",
  },
  {
    label: "Project Settings",
    icon: SettingsIcon,
    path: "/admin/project-settings",
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