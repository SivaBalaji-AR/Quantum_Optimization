HOW TO RUN THIS

1.Clone this

2.For backend, go to the backend folder and in commmad line use the cmd

    python -m venv venv
  
    venv\Scripts\activate
  
    pip install --upgrade pip
    
    pip install -r requirements.txt

    uvicorn main:app --reload
    
3.For Frontend, go to the Frontend Folder and in commad line use the cmd

    npm install
  
    npm start

4. If something happens in the backend because of qiskit, in the venv use this commands

    pip install qiskit-algorithms qiskit-optimization qiskit-aer

    (venv) PS C:\Users\anand\OneDrive\Documents\GitHub\Quantum_Optimization\backend> pip install qiskit-aer