import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

export const palette = {
  background: "#F5F7FB",
  surface: "#FFFFFF",
  primary: "#625BF6",
  text: "#18212F",
  muted: "#6B7280",
  success: "#22C55E",
  border: "#E5E7EB",
};

export function Card({ children }: React.PropsWithChildren) {
  return <View style={styles.card}>{children}</View>;
}

export function PrimaryButton({ title, onPress, disabled = false }: { title: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable style={[styles.button, disabled && styles.disabled]} onPress={onPress} disabled={disabled}>
      <Text style={styles.buttonText}>{title}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: palette.surface, borderRadius: 20, padding: 18, marginBottom: 14, shadowColor: "#101828", shadowOpacity: 0.06, shadowRadius: 12, elevation: 2 },
  button: { backgroundColor: palette.primary, paddingVertical: 14, paddingHorizontal: 18, borderRadius: 14, alignItems: "center" },
  buttonText: { color: "white", fontWeight: "700", fontSize: 16 },
  disabled: { opacity: 0.5 },
});

