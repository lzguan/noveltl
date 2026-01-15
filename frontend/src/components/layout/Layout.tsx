import { Outlet } from 'react-router';
import { Navbar } from './Navbar';

export const Layout = () => (
    <div>
        <Navbar />
        <main>
            <Outlet />
        </main>
    </div>
);