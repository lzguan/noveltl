import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

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
import { routeTo } from "@/routes";
import {
	ChevronDownIcon,
	LogInIcon,
	LogOutIcon,
	PencilLineIcon,
	UserIcon,
} from "lucide-react";

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

function AppShell() {
	const { user, logout } = useAuth();
	const navigate = useNavigate();

	function handleLogout() {
		logout();
		navigate("/login", { replace: true })?.catch((err) => {
			console.error("Failed to navigate after logout", err);
		});
	}

	return (
		<div className="flex h-screen flex-col bg-background">
			<header className="border-b bg-background/95 backdrop-blur shrink-0">
				<div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-6 py-3 lg:flex-row lg:items-center lg:justify-between">
					<div className="flex items-center gap-3 min-w-0">
						<Link
							to={routeTo.edit.dashboard()}
							className="text-lg font-semibold tracking-tight shrink-0"
						>
							NovelTL
						</Link>
						<span className="text-sm text-muted-foreground truncate hidden sm:block">
							Edit chapters and manage translation labels.
						</span>
					</div>

					<div className="flex items-center gap-2 flex-wrap">
						<Button asChild variant="ghost" size="sm">
							<NavLink to={routeTo.edit.dashboard()} end>
								<PencilLineIcon data-icon="inline-start" className="size-4" />
								Edit Home
							</NavLink>
						</Button>

						{user ? (
							<DropdownMenu>
								<DropdownMenuTrigger asChild>
									<Button variant="outline" size="sm">
										<UserIcon data-icon="inline-start" className="size-4" />
										{user.userName}
										<ChevronDownIcon className="size-3.5 opacity-50" />
									</Button>
								</DropdownMenuTrigger>
								<DropdownMenuContent align="end" className="w-48">
									<DropdownMenuLabel>{user.userName}</DropdownMenuLabel>
									<DropdownMenuSeparator />
									<DropdownMenuItem onClick={handleLogout}>
										<LogOutIcon className="size-4" />
										Log Out
									</DropdownMenuItem>
								</DropdownMenuContent>
							</DropdownMenu>
						) : (
							<Button asChild variant="outline" size="sm">
								<Link to="/login">
									<LogInIcon data-icon="inline-start" className="size-4" />
									Login
								</Link>
							</Button>
						)}
					</div>
				</div>
			</header>

			<div className="flex-1 min-h-0 overflow-hidden">
				<Outlet />
			</div>
		</div>
	);
}

export { AppShell };
