import "./App.css";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppRoutes } from "./routes";
import { SourceWorksPage } from "./view/pages/SourceWorksPage";
import { ViewShell, EditShell } from "./components/navigation/AppShell";
import { DashboardPage } from "./dashboard/pages/DashboardPage";
import { Suspense, lazy } from "react";
import { LoginPage } from "./auth/pages/LoginPage";
import { SourceWorkDetailsPage } from "./view/pages/SourceWorkDetailsPage";
import { NovelsPage } from "./view/pages/NovelsPage";
import { NovelDetailsPage } from "./view/pages/NovelDetailsPage";

const EditNovelPage = lazy(() =>
	import("./edit/pages/EditNovelPage").then((mod) => ({ default: mod.EditNovelPage })),
);
const EditDashboardPage = lazy(() =>
	import("./edit/pages/EditDashboardPage").then((mod) => ({ default: mod.EditDashboardPage })),
);

function App() {
	return (
		<Routes>
			<Route path={AppRoutes.ROOT} element={<Navigate to={AppRoutes.DASHBOARD} replace />} />
			<Route path={AppRoutes.LOGIN} element={<LoginPage />} />
			<Route element={<ViewShell />}>
				<Route path={AppRoutes.DASHBOARD} element={<DashboardPage />} />
				<Route path={AppRoutes.VIEW.SOURCEWORKS} element={<SourceWorksPage />} />
				<Route
					path={AppRoutes.VIEW.SOURCEWORK_DETAILS}
					element={<SourceWorkDetailsPage />}
				/>
				<Route path={AppRoutes.VIEW.NOVELS} element={<NovelsPage />} />
				<Route path={AppRoutes.VIEW.NOVEL_DETAILS} element={<NovelDetailsPage />} />
			</Route>
			<Route element={<EditShell />}>
				<Route
					path={AppRoutes.EDIT.DASHBOARD}
					element={
						<Suspense fallback={<div>Loading...</div>}>
							<EditDashboardPage />
						</Suspense>
					}
				/>
				<Route
					path={AppRoutes.EDIT.NOVEL}
					element={
						<Suspense fallback={<div>Loading...</div>}>
							<EditNovelPage />
						</Suspense>
					}
				/>
			</Route>
		</Routes>
	);
}

export { App };
