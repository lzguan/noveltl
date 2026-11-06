import { createContext, useContext } from "react";

/** Whether the right-panel tab containing this content is shown; true outside any tab. */
export const RightPanelTabActiveContext = createContext(true);

/** Kept-mounted tabs stay rendered while hidden; use this to pause background work there. */
export function useRightPanelTabActive() {
	return useContext(RightPanelTabActiveContext);
}
