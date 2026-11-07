import { createContext, useContext } from "react";

export const RightPanelTabActiveContext = createContext(true);

export function useRightPanelTabActive() {
	return useContext(RightPanelTabActiveContext);
}
