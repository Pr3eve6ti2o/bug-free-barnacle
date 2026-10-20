import { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Page } from '@/components/Page.tsx';

export const ErrorPage: FC = () => {
  const navigate = useNavigate();

  return (
    <Page back={false}>
      <div className="fly-page-container">
        <div className="flex flex-col items-center justify-center h-[80vh] p-4">
          <h1 className="text-3xl font-bold text-white mb-4">Something went wrong</h1>
          <p className="text-white text-center mb-8 max-w-md">
            We couldn't load that page or connect to the game server.
            Please check your connection and try again.
          </p>
          <button
            className="bg-[#f5c518] hover:bg-[#ffd83d] text-[#06070c] px-8 py-3 rounded-full text-lg font-semibold"
            onClick={() => window.location.reload()}
          >
            Reload page
          </button>
          <button
            className="text-[#f5c518] underline underline-offset-4 mt-4 hover:text-[#ffd83d]"
            onClick={() => navigate('/SpaceHunter/fly')}
          >
            Back to the game
          </button>
        </div>
      </div>
    </Page>
  );
};
