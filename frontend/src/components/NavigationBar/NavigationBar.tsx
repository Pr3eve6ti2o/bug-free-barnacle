import { FC, useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Pickaxe, ClipboardList, User } from 'lucide-react';
import './NavigationBar.css';

enum Page {
    Fly = 'Fly',
    Tasks = 'Tasks',
    Me = 'Me',
}

export const NavigationBar: FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const [currentPage, setCurrentPage] = useState<Page | null>(null);

    const getCurrentPageFromPath = (path: string): Page | null => {
        const segment = path
            .split(/[?#]/)[0]
            .split('/')
            .filter((part) => part.length > 0)
            .pop()
            ?.toLowerCase();
        if (!segment) return null;
        const page = Object.values(Page).find((p) => p.toLowerCase() === segment);
        return page || null;
    };

    useEffect(() => {
        setCurrentPage(getCurrentPageFromPath(location.pathname));
    }, [location.pathname]);

    const pages = [
        { id: Page.Fly, icon: Pickaxe, title: 'Mining' },
        { id: Page.Tasks, icon: ClipboardList, title: 'Tasks' },
        { id: Page.Me, icon: User, title: 'Me' },
    ];

    const handlePageClick = (id: Page) => {
        setCurrentPage(id);
        navigate(`/SpaceHunter/${id.toLowerCase()}`);
        console.log(id);
    };

    return (
        <nav className="navbar">
            {pages.map((page) => {
                const Icon = page.icon;
                return (
                    <button
                        key={page.id}
                        onClick={() => handlePageClick(page.id)}
                        className={`navbar-button ${currentPage === page.id ? 'active' : 'inactive'}`}
                    >
                        <Icon size={21} strokeWidth={1.8} />
                        <span>{page.title}</span>
                    </button>
                );
            })}
        </nav>
    );
};