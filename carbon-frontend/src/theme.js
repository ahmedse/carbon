import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#4caf50" },
    secondary: { main: "#232526" },
    background: {
      default: "#f8f9fa"
    }
  },
  components: {
    MuiButton: { styleOverrides: { root: { borderRadius: 6 } } }
  }
});

export default theme;