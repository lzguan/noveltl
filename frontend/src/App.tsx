import "./App.css";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppRoutes } from "./routes";
import { AppShell } from "./components/navigation/AppShell";
import { Suspense, lazy } from "react";
import { LoginPage } from "./auth/pages/LoginPage";

const EditNovelPage = lazy(() =>
	import("./edit/pages/EditNovelPage").then((mod) => ({ default: mod.EditNovelPage })),
);
const EditDashboardPage = lazy(() =>
	import("./edit/pages/EditDashboardPage").then((mod) => ({ default: mod.EditDashboardPage })),
);
const SettingsPage = lazy(() =>
	import("./settings/pages/SettingsPage").then((mod) => ({ default: mod.SettingsPage })),
);

function App() {
	return (
		<Routes>
			<Route
				path={AppRoutes.ROOT}
				element={<Navigate to={AppRoutes.EDIT.DASHBOARD} replace />}
			/>
			<Route path={AppRoutes.LOGIN} element={<LoginPage />} />
			<Route element={<AppShell />}>
				<Route
					path={AppRoutes.EDIT.DASHBOARD}
					element={
						<Suspense fallback={<div>Loading...</div>}>
							<EditDashboardPage />
						</Suspense>
					}
				/>
				<Route
					path={AppRoutes.SETTINGS}
					element={
						<Suspense fallback={<div>Loading...</div>}>
							<SettingsPage />
						</Suspense>
					}
				/>
			</Route>
			<Route
				path={AppRoutes.EDIT.NOVEL}
				element={
					<Suspense fallback={<div>Loading...</div>}>
						<EditNovelPage />
					</Suspense>
				}
			/>
		</Routes>
	);
}

export { App };
