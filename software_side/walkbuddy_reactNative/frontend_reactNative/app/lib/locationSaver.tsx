import React, { createContext, useContext, useState } from "react";

type LocationContextType = {
  currentLocation: string;
  setCurrentLocation: (value: string) => void;
};

const CurrentLocationContext = createContext<LocationContextType | null>(null);

export function CurrentLocationProvider({ children }: { children: React.ReactNode }) {
  const [currentLocation, setCurrentLocation] = useState("");

  return (
    <CurrentLocationContext.Provider value={{ currentLocation, setCurrentLocation }}>
      {children}
    </CurrentLocationContext.Provider>
  );
}

export function useCurrentLocation() {
  const context = useContext(CurrentLocationContext);

  if (context === null) {
    throw new Error("useCurrentLocation must be used inside CurrentLocationProvider");
  }

  return context;
}
