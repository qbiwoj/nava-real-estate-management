import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import QueuePage from './pages/QueuePage'
import ThreadPage from './pages/ThreadPage'

const router = createBrowserRouter([
  { path: '/', element: <QueuePage /> },
  { path: '/threads/:id', element: <ThreadPage /> },
])

export default function App() {
  return <RouterProvider router={router} />
}
