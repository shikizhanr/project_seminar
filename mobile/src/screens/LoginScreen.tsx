import React, { useState } from "react";
import { Alert, KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from "react-native";
import { palette, PrimaryButton } from "../components/UI";
import { useAuth } from "../context/AuthContext";

export function LoginScreen() {
  const { api, setToken } = useAuth();
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("demo-password");
  const [name, setName] = useState("Новый пользователь");
  const [register, setRegister] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      const result = register ? await api.register(email, name, password) : await api.login(email, password);
      await setToken(result.access_token);
    } catch (error) {
      Alert.alert("Не удалось войти", error instanceof Error ? error.message : "Попробуйте снова");
    } finally { setLoading(false); }
  };

  return (
    <KeyboardAvoidingView style={styles.page} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.hero}><Text style={styles.logo}>◎</Text><Text style={styles.title}>Habit Coach</Text><Text style={styles.subtitle}>Маленькие действия. Устойчивый результат.</Text></View>
      <View style={styles.form}>
        {register && <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Как вас зовут" />}
        <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="Email" autoCapitalize="none" keyboardType="email-address" />
        <TextInput style={styles.input} value={password} onChangeText={setPassword} placeholder="Пароль" secureTextEntry />
        <PrimaryButton title={loading ? "Подождите…" : register ? "Создать аккаунт" : "Войти"} onPress={submit} disabled={loading} />
        <Text style={styles.switch} onPress={() => setRegister(!register)}>{register ? "Уже есть аккаунт? Войти" : "Нет аккаунта? Зарегистрироваться"}</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: palette.background, justifyContent: "center", padding: 24 },
  hero: { alignItems: "center", marginBottom: 40 }, logo: { fontSize: 58, color: palette.primary, fontWeight: "800" },
  title: { fontSize: 32, color: palette.text, fontWeight: "800" }, subtitle: { color: palette.muted, marginTop: 8 },
  form: { gap: 12 }, input: { backgroundColor: "white", borderWidth: 1, borderColor: palette.border, borderRadius: 14, padding: 15, fontSize: 16 },
  switch: { color: palette.primary, textAlign: "center", marginTop: 8, fontWeight: "600" },
});

