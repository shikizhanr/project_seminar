export type Habit = {
  id: number;
  title: string;
  description: string;
  color: string;
  target_days_per_week: number;
  is_active: boolean;
};

export type Dashboard = {
  active_habits: number;
  completed_today: number;
  overall_completion_rate: number;
  current_total_streak: number;
  xp: number;
  level: number;
  motivation: string;
  trend: { day: string; completed: number; planned: number }[];
};

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiClient {
  constructor(private getToken: () => string | null) {}

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail ?? "Ошибка сервера");
    }
    return response.status === 204 ? ({} as T) : response.json();
  }

  login(email: string, password: string) {
    return this.request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  register(email: string, displayName: string, password: string) {
    return this.request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, display_name: displayName, password }),
    });
  }

  habits() { return this.request<Habit[]>("/habits"); }
  dashboard() { return this.request<Dashboard>("/analytics/dashboard"); }
  createHabit(title: string, targetDays: number) {
    return this.request<Habit>("/habits", {
      method: "POST",
      body: JSON.stringify({ title, target_days_per_week: targetDays }),
    });
  }
  checkIn(habitId: number, completed = true) {
    return this.request(`/habits/${habitId}/check-ins`, {
      method: "PUT",
      body: JSON.stringify({ day: new Date().toISOString().slice(0, 10), completed }),
    });
  }
}

