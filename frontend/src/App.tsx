import "./App.css";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppRoutes } from "./routes";
import { LoginPage } from "./auth/pages/LoginPage";
import { SourceWorksPage } from "./view/pages/SourceWorksPage";
import { ViewShell, EditShell } from "./components/navigation/AppShell";
import { DashboardPage } from "./dashboard/pages/DashboardPage";
import { EditDashboardPage } from "./edit/pages/EditDashboardPage";
import { EditNovelPage } from "./edit/pages/EditNovelPage";
import { SourceWorkDetailsPage } from "./view/pages/SourceWorkDetailsPage";
import { NovelDetailsPage } from "./view/pages/NovelDetailsPage";
import { NovelsPage } from "./view/pages/NovelsPage";

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
				<Route path={AppRoutes.EDIT.DASHBOARD} element={<EditDashboardPage />} />
				<Route path={AppRoutes.EDIT.NOVEL} element={<EditNovelPage />} />
			</Route>
		</Routes>
	);
}

export { App };
