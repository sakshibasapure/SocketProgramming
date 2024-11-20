#CSC573: Internet Protcols
#Contributers: Sakshi Basapure(sbasapu) and Pankhi Saini(psaini2)
#Date: Oct 17, 2024

import socket
import sys
import numpy as np 
import time 

# # Check if enough command-line arguments are provided
# if len(sys.argv) != 3:
#     print("Usage: python auc_client.py <server_ip> <port>")
# Check if enough command-line arguments are provided (at least 3 arguments)
if len(sys.argv) < 4 or len(sys.argv) > 5:
    print("Usage: python auc_client_rdt.py <server_ip> <port> <udp_port> [<packet_loss_rate>]")
    sys.exit(1)

SERVER = sys.argv[1]  # Get the server IP from command line
PORT = int(sys.argv[2])  # Get the TCP port number from command line and convert it to an integer
UDP_PORT = int(sys.argv[3])  # Get the UDP port number from command line and convert it to an integer
PACKET_LOSS_RATE = float(sys.argv[4]) if len(sys.argv) == 5 else 0.0  # Default to 0.0 if not provided

def seller_status(seller_client, msg):
    # This function checks the status of the auction request from the seller
    if msg == "Server: Invalid auction request!":
        print(msg)
        auction_request = input("Please submit auction request: ")
        seller_client.send(auction_request.encode())
        response = seller_client.recv(1024).decode()
        seller_status(seller_client, response)
    elif msg == "Server: Auction Start.":
        print("Server: Auction Start")
        return

def handle_seller(seller_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Seller]") 
    auction_request = input("Please submit auction request: ")

    seller_client.send(auction_request.encode())
    response = seller_client.recv(1024).decode()
    
    seller_status(seller_client, response)

    while True:
        # print("Server: Auction Start.")
        response = seller_client.recv(1024).decode()
        if "Auction Start" in response:
            print(response)
            bidding_information = input()
            seller_client.send(bidding_information.encode())
            auctioneer_response = seller_client.recv(1024).decode()
            print(auctioneer_response)
            break

        elif "Auction finished" in response:
            # Auction has finished, print the notification message from the server
            print("Auction is finished. Here is the result:")
            print(response)

            winner_ip = seller_client.recv(1024).decode()  # Winning Buyer IP addr
            print(f"Winner IP address is {winner_ip}")
            
            # Step 1: Create UDP socket for data transfer to Winning Buyer
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            print("UDP socket openned for RDT.")

            # Read the file to be sent
            with open("tosend.file", "rb") as file:
                file_data = file.read()

            file_length = len(file_data)
            print(f"Start sending file.")

            # Send file in chunks (Stop-and-Wait RDT)
            chunk_size = 2000
            total_chunks = len(file_data) // chunk_size + (1 if len(file_data) % chunk_size else 0)

             # Send initial control message with the total file size
            control_message = f"0 {file_length}".encode() 
            udp_socket.sendto(control_message, (winner_ip, UDP_PORT))
            print(f"Sending control seq 0: start {file_length}")

            seq_num = 1

            for i in range(total_chunks):
                start = i * chunk_size
                if start + chunk_size > file_length:
                    end = file_length
                else:
                    end = start + chunk_size
                chunk = file_data[start:end]
                print(f"Sending data seq {seq_num}: {end} / {file_length}")
                while True:
                    # Send chunk with sequence number
                    message = f"{seq_num} 1 ".encode() + chunk
                    udp_socket.sendto(message, (winner_ip, UDP_PORT))
                        
                    # Wait for ACK
                    udp_socket.settimeout(2)
                    try:
                        ack, _ = udp_socket.recvfrom(1024)

                        # Simulate packet loss
                        flag = np.random.binomial(n=1, p=PACKET_LOSS_RATE)
                        if flag == 1:
                            # Discard the ACK
                            print(f"ACK dropped: {seq_num}")
                            continue  # Wait for the next ACK or timeout
                        
                        ack_num = int(ack.decode().split()[0])
                        if ack_num == seq_num:
                            # print(f"Received ACK for chunk {seq_num}")
                            print(f"ACK received: {ack_num}")
                            # Toggle sequence number between 0 and 1 after receiving ACK
                            seq_num = 1 - seq_num
                            break
                    except socket.timeout:
                        print(f"Msg re-sent: {seq_num}")

            # End-of-transmission
            udp_socket.sendto(b"fin", (winner_ip, UDP_PORT))
            print("File transmission completed.")
            udp_socket.close()
            break

        # Handle empty response when the server closes the connection
        if response == "":
            print("Server has closed the connection.")
            break
            

    seller_client.close()

def check_bid_status(buyer_client, msg):
    if msg == "Server: Invalid bid. Please submit a positive integer!":
        bid = input("Please submit you bid:")
        buyer_client.send(bid.encode())
        response = buyer_client.recv(1024).decode()
        check_bid_status(buyer_client, response)
    else:
        return

def handle_buyer(buyer_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Buyer]") 

    while True:
        role_message = buyer_client.recv(1024).decode()

        # Check if the server sent an empty message (connection closed)
        if not role_message:
            print("Connection closed by the server.")
            break

        print(role_message)  # Print all messages received

        if "The bidding has started!" in role_message:
            while True:  # Continue to accept bids until a valid bid is received
                bid = input("Please submit your bid: ")
                buyer_client.send(bid.encode())
                response = buyer_client.recv(1024).decode()  # Receive the server's response
                
                # Check if the server sent an empty message (connection closed)
                if not response:
                    print("Connection closed by the server.")
                    break

                if response == "Server: Bid received. Please wait...":
                    print(response)
                    break  # Exit the inner loop once a valid bid has been submitted
                elif response == "Server: Invalid bid. Please submit a positive integer!":
                    print("Server: Invalid bid. Please submit a positive integer!")
            
            # After submitting a bid, wait for the auction results
            while True:
                auction_result = buyer_client.recv(1024).decode()  # Listen for the auction result
                
                # Check if the server sent an empty message (connection closed)
                if not auction_result:
                    print("Connection closed by the server.")
                    break
                
                # Check for the complete auction finished message for both winners and losers
                if "You won" in auction_result:
                    seller_ip = buyer_client.recv(1024).decode()
                    buyer_ip = buyer_client.getsockname()[0]

                    print(f"Seller IP address is {seller_ip}")

                    # Step 1: Create UDP socket to receive file
                    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp_socket.bind((buyer_ip, UDP_PORT))
                    print("Winning Buyer is ready to receive data...")

                    received_data = []
                    expected_seq = 1
                    received_size = 0  # Initialize received file size counter
                    print("UDP socket opened for RDT.")  
                    print("Start receiving file.")

                    # Initialize time tracking
                    start_time = time.time()  # Record the start time of file transfer

                    while True:
                        data, addr = udp_socket.recvfrom(2048)
                        parts = data.decode(errors='ignore').split()
                        if parts[0] == "fin":
                            break

                        seq_num = int(parts[0])
                        # Simulate packet loss
                        flag = np.random.binomial(n=1, p=PACKET_LOSS_RATE)
                        if flag == 1:
                            # Discard the message
                            print(f"Pkt dropped: {seq_num}")
                            continue
                            



                        if len(parts) == 2 and parts[0] == '0':
                            # First message, receiving control message with file length
                            file_length = int(parts[1])  # Extract file length from the control message
                            print(f"Msg received: 0")  # First message received with sequence 0
                            print(f"Ack sent: 0")  # Send ACK for the first message
                            udp_socket.sendto(f"0 ack".encode(), addr)
                            expected_seq = 1
                            last_ack_sent = 0
                            continue

                        seq_num = int(parts[0])
                        if seq_num == expected_seq:
                            # Print received message sequence
                            print(f"Msg received: {seq_num}")
                            received_data.append(data[4:])
                            received_size += len(data[4:])  # Update received file size

                            # Print ACK sent and current received file size
                            print(f"Ack sent: {seq_num}")
                            print(f"Received data seq {seq_num}: {received_size} / {file_length}") 

                            udp_socket.sendto(f"{seq_num} ack".encode(), addr)
                            last_ack_sent = seq_num
                            expected_seq = 1 - expected_seq  # Toggle expected sequence between 0 and 1
                        else:
                            if PACKET_LOSS_RATE > 0.0:
                                # Print unexpected sequence information
                                print(f"Msg received with mismatched sequence number {seq_num}. Expecting {expected_seq}.")
                            
                            if last_ack_sent is not None:
                                udp_socket.sendto(f"{last_ack_sent} ack".encode(), addr)
                                if PACKET_LOSS_RATE > 0.0:
                                    print(f"Ack re-sent: {last_ack_sent}")

                    # Calculate and print time metrics after file transfer
                    end_time = time.time()  # Record the end time of file transfer
                    tct = end_time - start_time  # Total time taken (TCT) in seconds
                    at = received_size / tct  # Average throughput (AT) in bytes/second

                    # Save the received file
                    with open("recved.file", "wb") as file:
                        file.write(b"".join(received_data))
                    
                    print(f"Transmission Finished: {received_size} bytes / {tct:.2f} seconds = {at:.2f} bps")
                    
                    
                    udp_socket.close()
                    break

        elif "Bidding on-going" in role_message:
            print("Bidding is already in progress. You cannot join this auction.")
            buyer_client.close()
            break

    # Ensure to close the buyer_client at the end if it wasn't closed earlier
    if buyer_client:
        buyer_client.close()


if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER, PORT))
    
    server_response = client_socket.recv(1024).decode()

    if server_response == 'seller':
        handle_seller(client_socket)
    elif server_response == 'buyer':
        handle_buyer(client_socket)
    else:
        print(server_response)