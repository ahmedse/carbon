// ---- Air-gap hardening (inserted into config.php by scripts/deploy.sh) ----
// Air-gap: never phone home
$CFG->noemailever                 = true;   // never try to send mail
$CFG->disableupdatenotifications  = true;   // no calls to download.moodle.org
$CFG->disableupdateautodeploy     = true;
$CFG->curlsecurityblockedhosts    = "0.0.0.0/0\n::/0"; // belt and braces
$CFG->preventexecpath             = true;   // no admin-editable exec paths

// Security
$CFG->cookiesecure   = true;
$CFG->cookiehttponly = true;
$CFG->forcelogin     = true;   // nothing visible without login
$CFG->loglifetime    = 0;      // keep logs forever (audit trail is the point)
$CFG->cronclionly    = true;   // cron only from CLI (host systemd timer)
$CFG->debug          = 0;
$CFG->debugdisplay   = 0;

// TLS terminated by Apache in-container (self-contained stack; no host proxy)
$CFG->sslproxy       = false;

// Forced settings the UI can't undo
$CFG->forced_plugin_settings = [
    'tool_mfa' => ['enabled' => 1, 'lockout' => 5],
];
