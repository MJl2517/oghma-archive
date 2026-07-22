import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallerContractTests(unittest.TestCase):
    def test_installer_exposes_requested_wizard_options(self):
        script = (ROOT / "installer" / "Oghma.iss").read_text(encoding="utf-8")
        self.assertIn("DisableDirPage=no", script)
        self.assertIn('Name: "desktopicon"', script)
        self.assertIn('Name: "autostart"', script)
        self.assertIn("Flags: unchecked", script)
        self.assertIn("{commonstartup}\\Oghma Archive", script)
        self.assertIn("PrivilegesRequired=admin", script)
        self.assertIn("[InstallDelete]", script)
        self.assertIn("cleanup-legacy-launchers.ps1", script)

    def test_installer_configures_and_removes_only_managed_domain_entry(self):
        script = (ROOT / "installer" / "configure-local-network.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("127.0.0.1 oghma.local # Oghma Archive", script)
        self.assertIn('"listenaddress=127.0.0.1", "listenport=80"', script)
        self.assertIn('"connectaddress=127.0.0.1", "connectport=5000"', script)
        self.assertIn("$ManagedEntryPattern", script)
        self.assertIn("Set-HostsContent -ForInstall $false", script)

    def test_packaged_application_contains_web_assets(self):
        spec = (ROOT / "installer" / "Oghma.spec").read_text(encoding="utf-8")
        self.assertIn('(str(project_root / "templates"), "templates")', spec)
        self.assertIn("static_datas", spec)
        self.assertIn('"img/themes/**/*.jpg"', spec)
        self.assertIn('project_root / "build" / "version-info.txt"', spec)
        self.assertIn('name="Oghma"', spec)


if __name__ == "__main__":
    unittest.main()
