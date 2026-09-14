import { SettingsPanel } from "@/components/settings-panel";

// No `dynamic = "force-dynamic"`: SettingsPanel is a client component that
// does all fetching in the browser, so the P4 static export only prerenders
// the empty shell. In Next 16 pages are dynamic by default, so the old flag
// was redundant.

export default function SettingsPage() {
  return <SettingsPanel />;
}
