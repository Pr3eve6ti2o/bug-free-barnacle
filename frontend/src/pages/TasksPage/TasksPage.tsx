import { FC, useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Page } from "@/components/Page.tsx";
import "./TasksPage.css";
import "@/components/p2e.css";
import { taskApi } from "@/services/api";
import { useTelegramUserId } from "@/hooks/useTelegramUser";
import Skeleton from "@/components/Skeleton/Skeleton.tsx";
import { ClipboardList } from "lucide-react";

interface Task {
  id: number;
  title: string;
  description: string;
  type: "daily" | "permanent";
  reward: number;
  condition_value: number;
  condition_type: string;
  reward_type: "token" | "multiplier";
  multiplier_pct: number;
  link_url?: string | null;
}

interface UserTask {
  id: number;
  task: Task;
  progress: number;
  is_completed: boolean;
  is_claimed: boolean;
}

export const TasksPage: FC = () => {
  const [tasks, setTasks] = useState<UserTask[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [claimingTask, setClaimingTask] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"permanent" | "daily" | "global">("permanent");
  const currentDateRef = useRef<number>(new Date().getDate());
  const navigate = useNavigate();

  const userId = useTelegramUserId() as number;

  // Проверка и сброс ежедневных заданий при необходимости
  const checkDailyReset = async () => {
    const now = new Date();
    const currentDay = now.getDate();
    
    // Если день изменился с момента последней проверки
    if (currentDay !== currentDateRef.current) {
      console.log("Day has changed - checking daily reset");
      currentDateRef.current = currentDay;
      
      try {
        await taskApi.checkDailyReset(userId);
      } catch (error) {
        console.error("Error checking daily reset:", error);
      }
    }
  };

  const fetchTasks = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Проверяем сброс ежедневных заданий
      await checkDailyReset();
      
      // Проверяем прогресс заданий
      await taskApi.checkTasksProgress(userId);
      
      // Получаем обновленные задания
      const userTasks = await taskApi.getUserTasks(userId);
      setTasks(
        userTasks.map((userTask) => ({
          ...userTask,
          task: {
            ...userTask.task,
            type: userTask.task.type.toLowerCase() as "daily" | "permanent",
          },
        }))
      );
    } catch (error) {
      console.error("Error fetching tasks:", error);
      setError("Could not load tasks. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    
    // Устанавливаем интервал для периодической проверки смены дня
    const intervalId = setInterval(() => {
      checkDailyReset();
    }, 60000); // Проверяем каждую минуту
    
    return () => {
      clearInterval(intervalId);
    };
  }, [userId]);

  // Функция для обработки нажатия на кнопку задания
  const handleTaskAction = async (userTask: UserTask) => {
    if (userTask.is_completed && !userTask.is_claimed) {
      try {
        setClaimingTask(userTask.id);
        setActionError(null);
        // Вызываем API для получения награды
        const result = await taskApi.claimTaskReward(userId, userTask.id);
        if (!result.success) throw new Error("Claim rejected by server");
        // Обновляем список заданий
        await fetchTasks();
      } catch (error) {
        console.error("Error claiming reward:", error);
        window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred("error");
        setActionError("Could not claim the reward. Please try again.");
        await fetchTasks();
      } finally {
        setClaimingTask(null);
      }
    } else if (userTask.is_claimed) {
      return; // already done
    } else if (userTask.task.link_url) {
      // External action (e.g. open the bot): open it, then re-verify progress
      const url = userTask.task.link_url;
      if (window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(url);
      } else {
        window.open(url, "_blank");
      }
      window.setTimeout(() => { void fetchTasks(); }, 4000);
    } else {
      // In-game action — send the player to the Mining tab
      navigate("/SpaceHunter/fly");
    }
  };

  // Only the active tab (Global shows everything), then: claimable first,
  // then in progress, then claimed
  const filteredTasks = [...tasks]
    .filter((t) => activeTab === "global" || t.task.type === activeTab)
    .sort((a, b) => {
      const rank = (t: UserTask) => (t.is_claimed ? 2 : t.is_completed ? 0 : 1);
      return rank(a) - rank(b);
    });

  return (
    <Page back={false}>
      <div className="tasks-page-container">
        <div className="tasks-head">
          <div style={{ fontWeight: 600, fontSize: 22, letterSpacing: "-0.01em" }}>
            {activeTab === "permanent" ? "Starter tasks" : activeTab === "daily" ? "Daily tasks" : "Global tasks"}
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,.62)", marginTop: 4, lineHeight: 1.45 }}>
            {activeTab === "permanent"
              ? "Earn CSM tokens or permanent mining-power boosts. Progress is checked automatically — rewards unlock as soon as a task is done."
              : activeTab === "daily"
                ? "Fresh targets every day for extra CSM tokens. Progress is checked automatically — rewards unlock as soon as a task is done, and reset when a new day begins."
                : "Every task in the game, in one place — starter and daily together. Progress is checked automatically, and rewards unlock as soon as a task is done."}
          </div>
        </div>

        <div
          role="tablist"
          aria-label="Task categories"
          style={{ display: "flex", gap: 8, margin: "14px 0 16px" }}
        >
          {(["permanent", "daily", "global"] as const).map((tabKey) => {
            const isActive = activeTab === tabKey;
            const count = tabKey === "global" ? tasks.length : tasks.filter((t) => t.task.type === tabKey).length;
            return (
              <button
                key={tabKey}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tabKey)}
                style={{
                  padding: "8px 16px",
                  borderRadius: 999,
                  border: isActive ? "1px solid #f5c518" : "1px solid rgba(255,255,255,.12)",
                  background: isActive ? "#f5c518" : "#10121c",
                  color: isActive ? "#06070c" : "rgba(255,255,255,.78)",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "background .15s ease, color .15s ease",
                }}
              >
                {tabKey === "permanent" ? "Starter" : tabKey === "daily" ? "Daily" : "Global"} ({count})
              </button>
            );
          })}
        </div>

        {actionError && (
          <div
            role="alert"
            style={{
              marginBottom: 12,
              padding: "12px 14px",
              borderRadius: 12,
              background: "#10121c",
              border: "1px solid rgba(255,255,255,.07)",
              color: "rgba(255,255,255,.86)",
              fontSize: 13,
            }}
          >
            {actionError}
          </div>
        )}

        {isLoading ? (
          <div className="tasks-list">
            {[0, 1, 2].map((row) => (
              <Skeleton key={row} height={64} radius={16} width="100%" />
            ))}
          </div>
        ) : error ? (
          <div
            role="alert"
            style={{
              padding: 14,
              borderRadius: 16,
              background: "rgba(255, 90, 90, 0.08)",
              border: "1px solid rgba(255, 90, 90, 0.25)",
              textAlign: "center",
            }}
          >
            <div style={{ marginBottom: 10 }}>{error}</div>
            <button className="claim-button" onClick={() => void fetchTasks()}>
              Retry
            </button>
          </div>
        ) : filteredTasks.length === 0 ? (
          <div
            className="no-tasks"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 8,
              textAlign: "center",
            }}
          >
            <ClipboardList size={28} color="#f5c518" />
            <p>
              {activeTab === "permanent"
                ? "All starter tasks completed — nice work, pilot!"
                : activeTab === "daily"
                  ? "All daily tasks completed — come back tomorrow, pilot!"
                  : "No tasks here yet — new tasks are added regularly, pilot!"}
            </p>
            <p className="no-tasks-sub" style={{ opacity: 0.6, fontSize: "0.875rem" }}>
              New tasks are added regularly — check back soon, or keep mining in the meantime.
            </p>
          </div>
        ) : (
          <div className="tasks-list-container">
            <div className="tasks-list">
              {filteredTasks.map((userTask) => (
                <div key={userTask.id} className={`task-item${userTask.is_claimed ? ' task-done' : ''}`}>
                  <div className="task-info">
                    <div className="task-header">
                      <span className="task-description">{userTask.task.title}</span>
                      {userTask.task.reward_type === 'multiplier' ? (
                        <span className="task-reward task-reward-boost tnum">
                          +{userTask.task.multiplier_pct}% mining power
                        </span>
                      ) : (
                        <span className="task-reward tnum">
                          +{userTask.task.reward} CSM
                        </span>
                      )}
                    </div>
                    <div className="task-sub">{userTask.task.description}</div>
                    <div className="task-progress-bar">
                      <div
                        className="task-progress-fill"
                        style={{
                          width: `${Math.min(100, (userTask.progress / userTask.task.condition_value) * 100)}%`
                        }}
                      ></div>
                      <span className="task-progress-text tnum">
                        {Math.min(userTask.progress, userTask.task.condition_value)}/{userTask.task.condition_value}
                      </span>
                    </div>
                  </div>
                  <button
                    className={`task-button ${userTask.is_completed && !userTask.is_claimed ? 'claim-ready' : ''} ${claimingTask === userTask.id ? 'loading' : ''}`}
                    onClick={() => handleTaskAction(userTask)}
                    disabled={claimingTask !== null || userTask.is_claimed}
                  >
                    {claimingTask === userTask.id
                      ? '...'
                      : userTask.is_claimed
                        ? 'Done'
                        : userTask.is_completed
                          ? 'Claim'
                          : userTask.task.link_url
                            ? 'Open'
                            : 'Go'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
        {tasks.some(t => t.is_claimed) && (
          <div className="tasks-history">
            <div className="sh-label" style={{ margin: '18px 0 8px' }}>History</div>
            {tasks.filter(t => t.is_claimed).map(t => (
              <div key={t.id} className="task-item task-done">
                <div className="task-info">
                  <span className="task-description">{t.task.title}</span>
                </div>
                <span className="task-reward tnum">{t.task.reward_type === 'multiplier' ? `+${t.task.multiplier_pct}% mining power` : `+${t.task.reward} CSM`}</span>
                <span className="history-badge">Claimed</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Page>
  );
};