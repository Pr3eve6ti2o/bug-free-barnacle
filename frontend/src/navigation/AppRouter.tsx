import {lazy, Suspense, useEffect} from "react";
import {Navigate, Route, Routes, useLocation, useNavigate} from "react-router-dom";
import {FlyPage} from "@/pages/FlyPage/FlyPage.tsx";
import {BoostPage} from "@/pages/BoostPage/BoostPage.tsx";
import {TasksPage} from "@/pages/TasksPage/TasksPage.tsx";
import {MePage} from "@/pages/MePage/MePage.tsx";
import {DropPage} from "@/pages/DropPage/DropPage.tsx";
import {ArcadePage} from "@/pages/ArcadePage/ArcadePage.tsx";
import {ErrorPage} from "@/pages/ErrorPage/ErrorPage.tsx";
import {RequireTelegram} from "@/components/TelegramGate.tsx";

const AdminPage = lazy(() =>
    import("@/pages/AdminPage/AdminPage.tsx").then((module) => ({default: module.AdminPage}))
);

const FLY_PATH = "/SpaceHunter/fly";
const ERROR_PATH = "/SpaceHunter/error";

type BackButtonLike = {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
};

function getTelegramBackButton(): BackButtonLike | undefined {
    return (window as unknown as {Telegram?: {WebApp?: {BackButton?: BackButtonLike}}})
        .Telegram?.WebApp?.BackButton;
}

export function TelegramBackButton() {
    const location = useLocation();
    const navigate = useNavigate();
    const isFlyRoot = location.pathname === FLY_PATH;

    useEffect(() => {
        const backButton = getTelegramBackButton();
        if (!backButton) return;

        if (isFlyRoot) {
            backButton.hide();
            return;
        }

        const handleBack = () => {
            if (window.history.length > 1) {
                navigate(-1);
            } else {
                navigate(FLY_PATH, {replace: true});
            }
        };

        backButton.show();
        backButton.onClick(handleBack);

        return () => {
            backButton.offClick(handleBack);
            backButton.hide();
        };
    }, [isFlyRoot, navigate]);

    return null;
}

export function AppRouter() {
    return (
        <>
            <TelegramBackButton />
            <Suspense fallback={<div style={{minHeight: "100vh", background: "#06070c"}} />}>
                <Routes>
                    <Route path="/SpaceHunter" element={<Navigate to={FLY_PATH} replace />} />
                    <Route path="/SpaceHunter/" element={<Navigate to={FLY_PATH} replace />} />
                    <Route path={FLY_PATH} element={<RequireTelegram><FlyPage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/boost" element={<RequireTelegram><BoostPage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/tasks" element={<RequireTelegram><TasksPage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/me" element={<RequireTelegram><MePage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/drop" element={<RequireTelegram><DropPage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/arcade" element={<RequireTelegram><ArcadePage /></RequireTelegram>} />
                    <Route path="/SpaceHunter/admin" element={<AdminPage />} />
                    <Route path={ERROR_PATH} element={<ErrorPage />} />
                    <Route path="*" element={<Navigate to={ERROR_PATH} replace />} />
                </Routes>
            </Suspense>
        </>
    );
}
