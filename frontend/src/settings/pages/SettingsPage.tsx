import { PublishingTargetsSection } from "@/publishing/components/PublishingTargetsSection";

export function SettingsPage() {
	return (
		<main className="h-full overflow-y-auto">
			<section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
				<header className="flex flex-col gap-2">
					<h1 className="text-4xl font-semibold tracking-tight">Settings</h1>
					<p className="max-w-3xl text-base text-muted-foreground">
						Configure publishing targets and workspace integrations.
					</p>
				</header>

				<PublishingTargetsSection />
			</section>
		</main>
	);
}
