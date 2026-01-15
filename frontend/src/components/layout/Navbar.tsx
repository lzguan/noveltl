import { Link, useNavigate } from 'react-router';
import { AppRoutes, routeTo } from '../../routes';
import { getToken, removeToken } from '../../api/token';

export const Navbar = () => {
    const navigate = useNavigate();
    const isLoggedIn = !!getToken();

    const handleLogout = () => {
        removeToken();
        navigate(AppRoutes.LOGIN);
    };

    return (
        <nav style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 24px',
            backgroundColor: '#333',
            color: '#fff'
        }}>
            <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
                <Link to={AppRoutes.DASHBOARD} style={{ color: '#fff', textDecoration: 'none', fontWeight: 'bold', fontSize: '1.2rem' }}>
                    NovelTL
                </Link>
                <Link to={routeTo.view.novels()} style={{ color: '#ccc', textDecoration: 'none' }}>
                    Library
                </Link>
                {isLoggedIn && (
                    <>
                        <Link to={routeTo.view.novels({ mine: true })} style={{ color: '#ccc', textDecoration: 'none' }}>
                            My Novels
                        </Link>
                        <Link to={routeTo.edit.novels()} style={{ color: '#ccc', textDecoration: 'none' }}>
                            Manage
                        </Link>
                    </>
                )}
            </div>
            <div>
                {isLoggedIn ? (
                    <button 
                        onClick={handleLogout}
                        style={{ padding: '8px 16px', background: 'transparent', color: '#fff', border: '1px solid #fff', borderRadius: '4px', cursor: 'pointer' }}
                    >
                        Logout
                    </button>
                ) : (
                    <Link to={AppRoutes.LOGIN} style={{ color: '#fff', textDecoration: 'none' }}>
                        Login
                    </Link>
                )}
            </div>
        </nav>
    );
};