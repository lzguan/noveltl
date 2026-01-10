import React, { useState } from 'react';
import { login } from '../api/auth'
import { useNavigate } from 'react-router-dom'
import { isAxiosError } from 'axios';

export const LoginPage = () => {
    const navigate = useNavigate();

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleLogin = async (e : React.FormEvent) => {
        e.preventDefault()
        setError('')
        const formData = new URLSearchParams()
        formData.append('username', username)
        formData.append('password', password)
        try {
            await login(formData)
            navigate('/dashboard')
        } catch(err) {
            if (isAxiosError(err)) {
                
                if (err.response) {
                    if (err.response.status === 401) {
                        setError("Incorrect username or password.");
                    } else if (err.response.status === 500) {
                        setError("Server error. Please try again later.");
                    } else {
                        setError(err.response.data.detail || "Login failed.");
                    }
                } 
                else if (err.request) {
                    setError("Cannot connect to server. Is the backend running?");
                }
            } 
            else {
                setError("An unexpected error occurred.");
            }
        }
    }


    return (
        <div style={{ padding: '2rem', maxWidth: '400px', margin: '0 auto' }}>
            <h2>Login</h2>

            {error && (
                <div style={{ 
                    color: 'red', 
                    marginBottom: '1rem', 
                    padding: '0.5rem', 
                    border: '1px solid red', 
                    borderRadius: '4px' 
                }}>
                    {error}
                </div>
            )}

            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                    <label htmlFor='username' style={{ display: 'block', marginBottom: '0.5rem' }}>Username</label>
                    <input
                        id="username"
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                        autoComplete='username'
                        style={{ width: '100%', padding: '0.5rem' }}
                    />
                </div>

                <div>
                    <label htmlFor='password' style={{ display: 'block', marginBottom: '0.5rem' }}>Password</label>
                    <input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        autoComplete='current-password'
                        style={{ width: '100%', padding: '0.5rem' }}
                    />
                </div>

                <button type="submit" style={{ padding: '10px', marginTop: '10px', cursor: 'pointer' }}>
                    Sign In
                </button>
            </form>
        </div>
    );
}