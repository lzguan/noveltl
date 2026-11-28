import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";

import { readUserMeUsersMeGet } from "@/api/endpoints/default/default";
import type { User } from "@/api/models";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AppRoutes, routeTo } from "@/routes";
import { ChevronDownIcon, LogInIcon, LogOutIcon, SettingsIcon, UserIcon } from "lucide-react";

function useAuth() {
	const [user, setUser] = useState<User | null>(null);

	useEffect(() => {
		const token = window.localStorage.getItem("access_token");
		if (!token) {
			return;
		}
		let ignore = false;
		readUserMeUsersMeGet()
			.then((res) => {
				if (!ignore && res.data) {
					setUser(res.data);
				}
			})
			.catch((err) => {
				console.error("Failed to fetch user data", err);
			})
			.finally(() => {});
		return () => {
			ignore = true;
		};
	}, []);

	function logout() {
		window.localStorage.removeItem("access_token");
		window.localStorage.removeItem("token_type");
		window.sessionStorage.removeItem("access_token");
		window.sessionStorage.removeItem("token_type");
		setUser(null);
	}

	return { user, logout };
}

function UserMenu() {
	const { user, logout } = useAuth();
	const navigate = useNavigate();

	function handleLogout() {
		logout();
		navigate("/login", { replace: true })?.catch((err) => {
			console.error("Failed to navigate after logout", err);
		});
	}

	if (!user) {
		return (
			<Button asChild variant="outline" size="sm" className="h-7 px-2.5 text-xs">
				<Link to="/login">
					<LogInIcon data-icon="inline-start" className="size-3.5" />
					Login
				</Link>
			</Button>
		);
	}

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="outline" size="sm" className="h-7 gap-1.5 px-2.5 text-xs">
					<UserIcon data-icon="inline-start" className="size-3.5" />
					{user.userName}
					<ChevronDownIcon className="size-3 opacity-50" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" className="w-48">
				<DropdownMenuLabel>{user.userName}</DropdownMenuLabel>
				<DropdownMenuSeparator />
				<DropdownMenuItem asChild>
					<Link to={AppRoutes.SETTINGS}>
						<SettingsIcon className="size-4" />
						Settings
					</Link>
				</DropdownMenuItem>
				<DropdownMenuSeparator />
				<DropdownMenuItem onClick={handleLogout}>
					<LogOutIcon className="size-4" />
					Log Out
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

function AppShell() {
	return (
		<div className="flex h-screen flex-col bg-background">
			<header className="shrink-0 border-b bg-background/95 backdrop-blur">
				<div className="mx-auto flex h-11 w-full max-w-6xl items-center justify-between gap-3 px-6">
					<Link
						to={routeTo.edit.dashboard()}
						className="shrink-0 text-sm font-semibold tracking-tight"
					>
						NovelTL
					</Link>
					<UserMenu />
				</div>
			</header>

			<div className="flex-1 min-h-0 overflow-hidden">
				<Outlet />
			</div>
		</div>
	);
}

export { AppShell, UserMenu };
