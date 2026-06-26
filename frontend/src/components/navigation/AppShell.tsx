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
import { cn } from "@/lib/utils";
import { routeTo } from "@/routes";
import {
	BookOpenIcon,
	ChevronDownIcon,
	LibraryIcon,
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

type AppShellProps = {
	title: string;
	subtitle: string;
	side: "view" | "edit";
	homeHref: string;
};

function AppShell({ title, subtitle, side, homeHref }: AppShellProps) {
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
							to={homeHref}
							className="text-lg font-semibold tracking-tight shrink-0"
						>
							{title}
						</Link>
						<span
							className={cn(
								"inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] shrink-0",
								side === "view"
									? "border-blue-200 bg-blue-50 text-blue-700"
									: "border-amber-200 bg-amber-50 text-amber-700",
							)}
						>
							{side}
						</span>
						<span className="text-sm text-muted-foreground truncate hidden sm:block">
							{subtitle}
						</span>
					</div>

					<div className="flex items-center gap-2 flex-wrap">
						<DropdownMenu>
							<DropdownMenuTrigger asChild>
								<Button variant="outline" size="sm">
									<LibraryIcon data-icon="inline-start" className="size-4" />
									Browse
									<ChevronDownIcon className="size-3.5 opacity-50" />
								</Button>
							</DropdownMenuTrigger>
							<DropdownMenuContent align="start" className="w-48">
								<DropdownMenuLabel>Browse</DropdownMenuLabel>
								<DropdownMenuItem asChild>
									<Link to={routeTo.view.sourceworks()}>
										<LibraryIcon className="size-4" />
										Source Works
									</Link>
								</DropdownMenuItem>
								<DropdownMenuItem asChild>
									<Link to={routeTo.view.novels()}>
										<BookOpenIcon className="size-4" />
										Novels
									</Link>
								</DropdownMenuItem>
							</DropdownMenuContent>
						</DropdownMenu>

						{side === "edit" && (
							<Button asChild variant="ghost" size="sm">
								<NavLink to={routeTo.edit.dashboard()} end>
									<PencilLineIcon data-icon="inline-start" className="size-4" />
									Edit Home
								</NavLink>
							</Button>
						)}

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

			<div
				className={cn(
					"flex-1 min-h-0",
					side === "edit" ? "overflow-hidden" : "overflow-y-auto",
				)}
			>
				<Outlet />
			</div>
		</div>
	);
}

function ViewShell() {
	return (
		<AppShell
			title="NovelTL"
			subtitle="Browse source works, novels, and chapter data."
			side="view"
			homeHref="/dashboard"
		/>
	);
}

function EditShell() {
	return (
		<AppShell
			title="NovelTL Edit"
			subtitle="Edit chapters and manage translation labels."
			side="edit"
			homeHref={routeTo.edit.dashboard()}
		/>
	);
}

export { ViewShell, EditShell };
