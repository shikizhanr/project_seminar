import React from "react";
import { ActivityIndicator, Text } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { AuthProvider, useAuth } from "./src/context/AuthContext";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { HabitsScreen } from "./src/screens/HabitsScreen";
import { LoginScreen } from "./src/screens/LoginScreen";
import { palette } from "./src/components/UI";

const Tabs = createBottomTabNavigator();

function Root() {
  const { token, ready } = useAuth();
  if (!ready) return <ActivityIndicator style={{ flex: 1 }} color={palette.primary} />;
  if (!token) return <LoginScreen />;
  return <NavigationContainer><Tabs.Navigator screenOptions={{ headerShown: false, tabBarActiveTintColor: palette.primary }}>
    <Tabs.Screen name="Привычки" component={HabitsScreen} options={{ tabBarIcon: ({ color }) => <Text style={{ color }}>✓</Text> }} />
    <Tabs.Screen name="Прогресс" component={DashboardScreen} options={{ tabBarIcon: ({ color }) => <Text style={{ color }}>▥</Text> }} />
  </Tabs.Navigator></NavigationContainer>;
}

export default function App() {
  return <SafeAreaProvider><AuthProvider><StatusBar style="dark" /><Root /></AuthProvider></SafeAreaProvider>;
}

