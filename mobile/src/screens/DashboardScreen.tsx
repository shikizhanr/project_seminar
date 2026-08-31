import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Dashboard } from "../api/client";
import { Card, palette } from "../components/UI";
import { useAuth } from "../context/AuthContext";

export function DashboardScreen() {
  const { api } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const load = async () => { setLoading(true); try { setData(await api.dashboard()); } finally { setLoading(false); } };
  useFocusEffect(useCallback(() => { load(); }, [api]));

  return <ScrollView style={styles.page} contentContainerStyle={styles.content} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
    <Text style={styles.heading}>Ваш прогресс</Text>
    <Card><Text style={styles.motivation}>{data?.motivation ?? "Загружаем рекомендацию…"}</Text></Card>
    <View style={styles.metrics}>
      <Card><Text style={styles.metric}>{data?.completed_today ?? 0}/{data?.active_habits ?? 0}</Text><Text style={styles.label}>сегодня</Text></Card>
      <Card><Text style={styles.metric}>{Math.round((data?.overall_completion_rate ?? 0) * 100)}%</Text><Text style={styles.label}>регулярность</Text></Card>
    </View>
    <Card><Text style={styles.cardTitle}>Последние 14 дней</Text><View style={styles.chart}>{data?.trend.map((point) => <View key={point.day} style={[styles.bar, { height: 8 + Math.min(70, point.completed * 22) }]} />)}</View></Card>
    <Card><Text style={styles.cardTitle}>Уровень {data?.level ?? 1}</Text><Text style={styles.label}>{data?.xp ?? 0} XP · суммарная серия {data?.current_total_streak ?? 0}</Text></Card>
  </ScrollView>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: palette.background }, content: { padding: 20, paddingTop: 56 },
  heading: { fontSize: 28, fontWeight: "800", color: palette.text, marginBottom: 18 }, motivation: { fontSize: 17, color: palette.text, lineHeight: 25 },
  metrics: { flexDirection: "row", gap: 12 }, metric: { fontSize: 26, fontWeight: "800", color: palette.primary }, label: { color: palette.muted, marginTop: 4 },
  cardTitle: { fontSize: 18, fontWeight: "700", color: palette.text }, chart: { height: 90, flexDirection: "row", alignItems: "flex-end", gap: 7, marginTop: 14 }, bar: { flex: 1, backgroundColor: palette.primary, borderRadius: 5 },
});

