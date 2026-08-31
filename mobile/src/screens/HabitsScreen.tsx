import React, { useCallback, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Habit } from "../api/client";
import { Card, palette, PrimaryButton } from "../components/UI";
import { useAuth } from "../context/AuthContext";

export function HabitsScreen() {
  const { api } = useAuth();
  const [habits, setHabits] = useState<Habit[]>([]);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [modal, setModal] = useState(false);
  const [title, setTitle] = useState("");
  const load = async () => setHabits((await api.habits()).filter((item) => item.is_active));
  useFocusEffect(useCallback(() => { load(); }, [api]));
  const check = async (id: number) => { try { await api.checkIn(id); setDone(new Set(done).add(id)); } catch { Alert.alert("Ошибка", "Не удалось сохранить отметку"); } };
  const create = async () => { if (!title.trim()) return; await api.createHabit(title.trim(), 7); setTitle(""); setModal(false); load(); };

  return <View style={styles.page}><ScrollView contentContainerStyle={styles.content}>
    <View style={styles.header}><Text style={styles.heading}>Сегодня</Text><Pressable style={styles.add} onPress={() => setModal(true)}><Text style={styles.addText}>＋</Text></Pressable></View>
    {habits.map((habit) => <Card key={habit.id}><View style={styles.row}><View style={[styles.dot, { backgroundColor: habit.color }]} /><View style={styles.body}><Text style={styles.title}>{habit.title}</Text><Text style={styles.meta}>{habit.target_days_per_week} раз в неделю</Text></View><Pressable style={[styles.check, done.has(habit.id) && styles.checked]} onPress={() => check(habit.id)}><Text style={styles.checkText}>{done.has(habit.id) ? "✓" : ""}</Text></Pressable></View></Card>)}
    {!habits.length && <Text style={styles.empty}>Добавьте первую привычку — начните с небольшого действия.</Text>}
  </ScrollView><Modal visible={modal} transparent animationType="fade"><View style={styles.overlay}><View style={styles.dialog}><Text style={styles.dialogTitle}>Новая привычка</Text><TextInput autoFocus value={title} onChangeText={setTitle} style={styles.input} placeholder="Например, прогулка 20 минут" /><PrimaryButton title="Добавить" onPress={create} /><Text style={styles.cancel} onPress={() => setModal(false)}>Отмена</Text></View></View></Modal></View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: palette.background }, content: { padding: 20, paddingTop: 56 }, header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 18 },
  heading: { fontSize: 28, fontWeight: "800", color: palette.text }, add: { width: 42, height: 42, backgroundColor: palette.primary, borderRadius: 14, alignItems: "center", justifyContent: "center" }, addText: { color: "white", fontSize: 27 },
  row: { flexDirection: "row", alignItems: "center" }, dot: { width: 12, height: 44, borderRadius: 8, marginRight: 14 }, body: { flex: 1 }, title: { fontSize: 17, fontWeight: "700", color: palette.text }, meta: { color: palette.muted, marginTop: 4 },
  check: { width: 36, height: 36, borderRadius: 18, borderWidth: 2, borderColor: palette.border, alignItems: "center", justifyContent: "center" }, checked: { backgroundColor: palette.success, borderColor: palette.success }, checkText: { color: "white", fontWeight: "900", fontSize: 20 }, empty: { color: palette.muted, textAlign: "center", marginTop: 80, lineHeight: 22 },
  overlay: { flex: 1, backgroundColor: "#0007", justifyContent: "center", padding: 24 }, dialog: { backgroundColor: "white", borderRadius: 22, padding: 22, gap: 14 }, dialogTitle: { fontSize: 22, fontWeight: "800" }, input: { borderWidth: 1, borderColor: palette.border, borderRadius: 14, padding: 14, fontSize: 16 }, cancel: { textAlign: "center", color: palette.muted, padding: 4 },
});

