import { Link } from 'react-router';
import { routeTo } from '../routes';
import { getToken } from '../api/token';

export const DashboardPage = () => {
    const isLoggedIn = !!getToken();

    return (
        <div style={{ maxWidth: '800px', margin: '0 auto', padding: '40px 20px' }}>
            <h1>Welcome to NovelTL</h1>
            <p style={{ color: '#666', marginBottom: '40px' }}>
                A platform for managing and translating novels.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '20px' }}>
                <DashboardCard 
                    title="Library" 
                    description="Browse public novels"
                    to={routeTo.view.novels()}
                />
                {isLoggedIn && (
                    <>
                        <DashboardCard 
                            title="My Novels" 
                            description="View novels you contribute to"
                            to={routeTo.view.novels({ mine: true })}
                        />
                        <DashboardCard 
                            title="Manage" 
                            description="Edit your novel projects"
                            to={routeTo.edit.novels()}
                        />
                    </>
                )}
            </div>
        </div>
    );
};

const DashboardCard = ({ title, description, to }: { title: string; description: string; to: string }) => (
    <Link to={to} style={{ textDecoration: 'none', color: 'inherit' }}>
        <div style={{
            padding: '24px',
            border: '1px solid #ddd',
            borderRadius: '8px',
            backgroundColor: '#fff',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            transition: 'box-shadow 0.2s',
        }}>
            <h3 style={{ margin: '0 0 8px 0' }}>{title}</h3>
            <p style={{ margin: 0, color: '#666', fontSize: '0.9rem' }}>{description}</p>
        </div>
    </Link>
);