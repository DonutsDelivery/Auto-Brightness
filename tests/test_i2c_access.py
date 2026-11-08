import os
import unittest
from dataclasses import replace
from unittest.mock import patch

import donut_monitor_common as common
from donut_monitor_common import I2CFacts, distro_family, plan_i2c_fix

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def facts(**overrides):
    base = I2CFacts(
        family="debian", devices=3, usable=False, module_loaded=True,
        node_group="root", node_group_rw=False, group_exists=False,
        user_in_group=False, session_in_group=False, rule_installed=False,
        modules_conf_installed=False, ddcutil_present=True,
    )
    return replace(base, **overrides)


class DistroFamilyTests(unittest.TestCase):
    def test_families_from_id_and_id_like(self):
        cases = [
            ({"ID": "arch"}, "arch"),
            ({"ID": "cachyos", "ID_LIKE": "arch"}, "arch"),
            ({"ID": "ubuntu", "ID_LIKE": "debian"}, "debian"),
            ({"ID": "linuxmint", "ID_LIKE": "ubuntu debian"}, "debian"),
            ({"ID": "fedora"}, "fedora"),
            ({"ID": "rocky", "ID_LIKE": "rhel centos fedora"}, "fedora"),
            ({"ID": "opensuse-tumbleweed", "ID_LIKE": "opensuse suse"}, "suse"),
            ({"ID": "nixos"}, "nixos"),
            ({"ID": "alpine"}, "other"),
            ({}, "other"),
        ]
        for release, expected in cases:
            self.assertEqual(distro_family(release), expected, release)

    def test_read_os_release_strips_quotes(self, ):
        with patch("builtins.open", unittest.mock.mock_open(read_data='ID=ubuntu\nID_LIKE="debian"\n# c\n')):
            self.assertEqual(common.read_os_release("x"), {"ID": "ubuntu", "ID_LIKE": "debian"})

    def test_missing_os_release_is_other(self):
        with patch("builtins.open", side_effect=OSError):
            self.assertEqual(distro_family(), "other")


class PlanTests(unittest.TestCase):
    def test_usable_means_no_problem(self):
        self.assertIsNone(plan_i2c_fix(facts(usable=True)))

    def test_missing_module_gives_modprobe_and_persistence(self):
        text = plan_i2c_fix(facts(devices=0, module_loaded=False))
        self.assertIn("sudo modprobe i2c-dev", text)
        self.assertIn("tee /etc/modules-load.d/i2c-dev.conf", text)

    def test_packaged_boot_config_skips_persistence_step(self):
        text = plan_i2c_fix(facts(devices=0, module_loaded=False, modules_conf_installed=True))
        self.assertIn("sudo modprobe i2c-dev", text)
        self.assertNotIn("tee", text)

    def test_module_loaded_without_nodes_points_at_gpu_driver(self):
        text = plan_i2c_fix(facts(devices=0, module_loaded=True))
        self.assertNotIn("modprobe", text)
        self.assertIn("/sys/bus/i2c/devices", text)

    def test_no_rule_no_group_gives_full_sequence_in_order(self):
        text = plan_i2c_fix(facts())
        order = [
            "sudo groupadd -r -f i2c",
            "sudo tee /etc/udev/rules.d/60-donut-monitor-i2c.rules",
            "sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=i2c-dev",
            "sudo usermod -aG i2c $USER",
            "log out and back in",
        ]
        positions = [text.index(part) for part in order]
        self.assertEqual(positions, sorted(positions))

    def test_installed_rule_only_needs_udev_reload(self):
        text = plan_i2c_fix(facts(family="arch", rule_installed=True, group_exists=True, user_in_group=True,
                                  session_in_group=True))
        self.assertIn("udevadm trigger", text)
        self.assertNotIn("tee /etc/udev", text)
        self.assertNotIn("usermod", text)
        self.assertNotIn("groupadd", text)

    def test_group_member_with_old_session_only_asked_to_relogin(self):
        text = plan_i2c_fix(facts(node_group="i2c", node_group_rw=True, group_exists=True,
                                  user_in_group=True, session_in_group=False, rule_installed=True))
        self.assertIn("Log out and back in", text)
        self.assertNotIn("sudo", text)

    def test_working_rule_but_not_in_group_gets_usermod_only(self):
        text = plan_i2c_fix(facts(node_group="i2c", node_group_rw=True, group_exists=True, rule_installed=True))
        self.assertIn("sudo usermod -aG i2c $USER", text)
        self.assertNotIn("udevadm", text)

    def test_unexplained_denial_suggests_listing_nodes(self):
        text = plan_i2c_fix(facts(node_group="i2c", node_group_rw=True, group_exists=True, user_in_group=True,
                                  session_in_group=True, rule_installed=True))
        self.assertIn("ls -l /dev/i2c-*", text)

    def test_nixos_gets_declarative_option(self):
        text = plan_i2c_fix(facts(family="nixos"))
        self.assertIn("hardware.i2c.enable = true;", text)
        self.assertNotIn("usermod", text)

    def test_missing_ddcutil_adds_family_install_command(self):
        expected = {
            "arch": "sudo pacman -S ddcutil",
            "debian": "sudo apt install ddcutil",
            "fedora": "sudo dnf install ddcutil",
            "suse": "sudo zypper install ddcutil",
        }
        for family, command in expected.items():
            self.assertIn(command, plan_i2c_fix(facts(family=family, ddcutil_present=False)), family)
        self.assertIn("with your package manager", plan_i2c_fix(facts(family="other", ddcutil_present=False)))
        self.assertNotIn("ddcutil is not installed", plan_i2c_fix(facts()))

    def test_rule_text_matches_shipped_udev_rule(self):
        with open(os.path.join(REPO, "udev", "60-donut-monitor-i2c.rules")) as handle:
            shipped = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertEqual(shipped, [common.I2C_RULE_TEXT])


class CollectFactsTests(unittest.TestCase):
    """collect_i2c_facts reads /dev, /etc/group and os.access. Mock all of it."""

    def run_collect(self, nodes, accessible, group_entry):
        import types

        stat_result = types.SimpleNamespace(st_gid=0, st_mode=0o20600)
        root = types.SimpleNamespace(gr_name="root")
        with patch("donut_monitor_common.glob.glob", return_value=nodes), \
                patch("donut_monitor_common.os.access", return_value=accessible), \
                patch("donut_monitor_common.os.stat", return_value=stat_result), \
                patch("donut_monitor_common.grp.getgrgid", return_value=root), \
                patch("donut_monitor_common.grp.getgrnam", side_effect=group_entry), \
                patch("donut_monitor_common.os.getgroups", return_value=[1000]), \
                patch("donut_monitor_common.distro_family", return_value="debian"):
            return common.collect_i2c_facts()

    def test_no_nodes(self):
        found = self.run_collect([], False, KeyError)
        self.assertEqual((found.devices, found.usable, found.node_group), (0, False, None))
        self.assertFalse(found.group_exists)

    def test_nodes_owned_by_root_without_group(self):
        found = self.run_collect(["/dev/i2c-0"], False, KeyError)
        self.assertEqual((found.devices, found.usable, found.node_group, found.node_group_rw), (1, False, "root", False))

    def test_group_membership_and_session(self):
        import types
        me = types.SimpleNamespace(pw_name="emil", pw_gid=1000)
        group = types.SimpleNamespace(gr_gid=985, gr_mem=["emil"])
        with patch("donut_monitor_common.pwd.getpwuid", return_value=me):
            found = self.run_collect(["/dev/i2c-0"], False, lambda name: group)
        self.assertTrue(found.group_exists)
        self.assertTrue(found.user_in_group)
        self.assertFalse(found.session_in_group)  # getgroups() is [1000], not 985

    def test_i2c_access_problem_ties_collect_and_plan(self):
        with patch("donut_monitor_common.collect_i2c_facts", return_value=facts(devices=0, module_loaded=False)):
            self.assertIn("modprobe i2c-dev", common.i2c_access_problem())
        with patch("donut_monitor_common.collect_i2c_facts", return_value=facts(usable=True)):
            self.assertIsNone(common.i2c_access_problem())


if __name__ == "__main__":
    unittest.main()
