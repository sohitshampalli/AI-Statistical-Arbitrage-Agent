import { MotionConfig } from "motion/react";
import { ProvenanceDrawer } from "./components/ProvenanceDrawer";
import { ProjectProvider } from "./context/project";
import { ComponentGallery } from "./pages/dev/ComponentGallery";
import { NotBuilt } from "./pages/NotBuilt";
import { GALLERY_PATH, ROUTES, useRoute } from "./router";
import { AppShell } from "./shell/AppShell";
import { TopBarProvider } from "./shell/TopBarContext";

export function App() {
  const route = useRoute();
  const known = ROUTES.find((r) => r.path === route.path);
  return (
    <MotionConfig reducedMotion="user">
      <ProjectProvider>
        <TopBarProvider>
          <AppShell current={route.path}>
            {route.path === GALLERY_PATH ? <ComponentGallery /> : <NotBuilt title={known?.label ?? "Page not found"} />}
          </AppShell>
          <ProvenanceDrawer />
        </TopBarProvider>
      </ProjectProvider>
    </MotionConfig>
  );
}
