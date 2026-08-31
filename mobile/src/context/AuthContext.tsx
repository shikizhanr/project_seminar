import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useContext, useMemo, useState } from "react";
import { ApiClient } from "../api/client";

type AuthContextValue = {
  token: string | null;
  ready: boolean;
  api: ApiClient;
  setToken: (value: string | null) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: React.PropsWithChildren) {
  const [token, updateToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  React.useEffect(() => {
    AsyncStorage.getItem("access_token").then((saved) => {
      updateToken(saved);
      setReady(true);
    });
  }, []);

  const api = useMemo(() => new ApiClient(() => token), [token]);
  const setToken = async (value: string | null) => {
    updateToken(value);
    if (value) await AsyncStorage.setItem("access_token", value);
    else await AsyncStorage.removeItem("access_token");
  };

  return <AuthContext.Provider value={{ token, ready, api, setToken }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

